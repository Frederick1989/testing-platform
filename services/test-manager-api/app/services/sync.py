"""Azure DevOps synchronization workflows (idempotent)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.azure.client import AzureClientBase, strip_html
from app.config import settings
from app.models.azure import AzureSyncLog, Iteration, WorkItem
from app.models.test import Defect
from app.repositories import azure as az_repo
from app.repositories import tests as tests_repo

logger = logging.getLogger("app.sync")

_CURRENT_ITERATION_NAMES = ("Current",)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _work_item_to_model(client: AzureClientBase, raw: dict[str, Any], *, now: datetime) -> dict:
    fields = raw.get("fields", {})
    assigned = fields.get("System.AssignedTo") or {}
    assigned_name = assigned.get("displayName", "") if isinstance(assigned, dict) else str(assigned)
    tags = [t.strip() for t in str(fields.get("System.Tags", "")).split(";") if t.strip()]
    return {
        "azure_id": int(raw["id"]),
        "type": fields.get("System.WorkItemType", ""),
        "title": fields.get("System.Title", ""),
        "description": strip_html(fields.get("System.Description", "") or ""),
        "acceptance_criteria_raw": "\n".join(
            strip_html(line)
            for line in str(fields.get(settings.azure_acceptance_criteria_field, "") or "").splitlines()
            if line.strip()
        ),
        "state": fields.get("System.State", ""),
        "assigned_to": assigned_name,
        "iteration_name": fields.get("System.IterationPath", "").split("\\")[-1],
        "area_path": fields.get("System.AreaPath", ""),
        "severity": fields.get("Microsoft.VSTS.Common.Severity", ""),
        "created_at": _parse_dt(fields.get("System.CreatedDate")),
        "updated_at": _parse_dt(fields.get("System.ChangedDate")),
        "resolved_at": (
            _parse_dt(fields.get("Microsoft.VSTS.Common.ResolvedDate"))
            or _parse_dt(fields.get("System.ClosedDate"))
        ),
        "closed_at": (
            _parse_dt(fields.get(settings.azure_closed_date_field))
            if settings.azure_closed_date_field
            else _parse_dt(fields.get("System.ClosedDate"))
            or _parse_dt(fields.get("Microsoft.VSTS.Common.ClosedDate"))
        ),
        "tags": tags,
        "url": fields.get("System.Url", ""),
        "parent_azure_id": fields.get("System.Parent"),
        "comment_count": int(fields.get("System.CommentCount") or 0),
        "last_synced_at": now,
    }


def _defect_type_names() -> set[str]:
    return {t.strip() for t in settings.azure_defect_types.split(",") if t.strip()}


def _map_severity(raw: str) -> str:
    text = (raw or "").lower()
    if "critical" in text:
        return "CRITICAL"
    if "high" in text:
        return "HIGH"
    if "medium" in text:
        return "MEDIUM"
    if "low" in text:
        return "LOW"
    return "MEDIUM"


def _map_state(raw: str) -> str:
    """Normalize Azure states (including Basic-process Kanban states) to the
    platform defect states so open/closed metrics stay correct."""
    text = (raw or "").strip()
    if not text:
        return "New"
    return {
        "To Do": "New",
        "Doing": "Active",
        "In Progress": "Active",
        "Done": "Closed",
    }.get(text, text)


def _defect_from_model(model: dict[str, Any]) -> dict:
    return {
        "azure_id": model["azure_id"],
        "title": model["title"],
        "description": model["description"],
        "severity": _map_severity(model["severity"]),
        "priority": "",
        "state": _map_state(model["state"]),
        "assigned_to": model["assigned_to"],
        "iteration_name": model["iteration_name"],
        "story_work_item_id": model["parent_azure_id"],
        "created_at": model["created_at"],
        "resolved_at": model["resolved_at"],
        "closed_at": model["closed_at"],
        "reopened_count": 0,
        "is_escaped": False,
        "tags": model["tags"],
        "url": model["url"],
        "last_synced_at": model["last_synced_at"],
    }


def _split_acceptance_criteria(raw: str) -> list[str]:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    items = [line for line in lines if not line.lower().startswith(("given ", "when ", "then ", "and ", "but ")) or True]
    # keep full AC sentences (Given/When/Then grouped) but split on numbered/bulleted lists
    sentences: list[str] = []
    for line in items:
        if line and line[0].isdigit() and ". " in line[:5]:
            sentences.append(line.split(". ", 1)[1])
        elif line.startswith(("-", "•", "*")):
            sentences.append(line.lstrip("-•* ").strip())
        elif line.endswith(":") or (sentences and len(line) < 120):
            sentences.append(line)
        else:
            sentences.append(line)
    return [s for s in sentences if s][:30]


def _sync_comments(session: Session, client: AzureClientBase,
                   work_item_pk: int, azure_id: int) -> int:
    raw_comments = client.get_work_item_comments(azure_id)
    count = 0
    for c in raw_comments[:50]:
        count += 1
        az_repo.upsert_comment(
            session,
            {
                "azure_comment_id": int(c.get("id", 0)),
                "work_item_id": work_item_pk,
                "author": (c.get("createdBy") or {}).get("displayName", "")
                if isinstance(c.get("createdBy"), dict) else "",
                "created_at": _parse_dt(c.get("createdDate")),
                "text": strip_html(c.get("text", "") or "")[:4000],
            },
        )
    return count


async def sync_iterations(session: Session, client: AzureClientBase) -> int:
    raw = await client.list_iterations()
    now = datetime.now(timezone.utc)
    current_path = None
    for item in raw:
        if item.get("name") in _CURRENT_ITERATION_NAMES:
            current_path = item.get("path")
    count = 0
    for item in raw:
        azure_id = str(item.get("id"))
        name = item.get("name", "")
        attributes = item.get("attributes", {}) if isinstance(item.get("attributes"), dict) else {}
        timeframe = str(attributes.get("timeFrame", "")).capitalize()
        # Azure marks the current sprint via timeFrame; fall back to the
        # "Current"-named placeholder when the attribute is absent.
        is_current = timeframe == "Current" or bool(
            current_path and item.get("path") == current_path
        )
        az_repo.upsert_iteration(
            session,
            {
                "azure_id": azure_id,
                "name": name,
                "path": item.get("path", ""),
                "state": timeframe,
                "start_date": _parse_dt(attributes.get("startDate")),
                "finish_date": _parse_dt(attributes.get("finishDate")),
                "is_current": is_current,
                "url": item.get("url", ""),
                "last_synced_at": now,
            },
        )
        count += 1
    _prune_iterations(session, {str(item.get("id")) for item in raw})
    return count


def _prune_iterations(session: Session, azure_ids: set[str]) -> int:
    """Delete iterations that no longer exist in Azure (e.g. demo sprints)."""
    if not azure_ids:
        return 0
    stale = list(
        session.scalars(select(Iteration).where(Iteration.azure_id.notin_(azure_ids)))
    )
    if not stale:
        return 0
    stale_ids = [i.id for i in stale]
    session.query(WorkItem).filter(WorkItem.iteration_id.in_(stale_ids)).update(
        {"iteration_id": None}, synchronize_session=False
    )
    session.query(Defect).filter(Defect.iteration_id.in_(stale_ids)).update(
        {"iteration_id": None}, synchronize_session=False
    )
    for row in stale:
        session.delete(row)
    return len(stale)


async def sync_work_items(session: Session, client: AzureClientBase, *, only: list[str] | None = None) -> int:
    types = only or az_repo.types_for_query()
    now = datetime.now(timezone.utc)
    type_clause = " OR ".join(
        [f"[System.WorkItemType] = '{t}'" for t in types]
    )
    wiql = (
        f"SELECT [System.Id], [System.WorkItemType], [System.Title], [System.State] "
        f"FROM WorkItems WHERE {type_clause} ORDER BY [System.CreatedDate] DESC"
    )
    raw_items = await client.query_work_items(wiql)
    defect_types = _defect_type_names()
    count = 0
    synced: list[tuple[Any, dict[str, Any]]] = []
    for raw in raw_items:
        if raw.get("id") is None:
            continue
        model = _work_item_to_model(client, raw, now=now)
        row = az_repo.upsert_work_item(session, model)
        session.flush()
        # keep iteration linkage
        if model["iteration_name"]:
            iteration = az_repo.get_iteration_by_name(session, model["iteration_name"])
            row.iteration_id = iteration.id if iteration else None
        # parse acceptance criteria into rows
        ac_texts = _split_acceptance_criteria(model["acceptance_criteria_raw"])
        if ac_texts:
            az_repo.upsert_acceptance_criteria(session, row.id, ac_texts)
        # comments
        if row.comment_count:
            _sync_comments(session, client, row.id, int(raw["id"]))
        # defect-typed items also land in the defects table (metric pipeline)
        if model["type"] in defect_types:
            defect = _defect_from_model(model)
            defect_row = tests_repo.upsert_defect(session, defect)
            if model["iteration_name"]:
                iteration = az_repo.get_iteration_by_name(session, model["iteration_name"])
                defect_row.iteration_id = iteration.id if iteration else None
        synced.append((row, model))
        count += 1
    if settings.azure_derive_acceptance_criteria_from_tasks:
        _derive_criteria_from_tasks(session, synced)
    return count


_CRITERIA_SOURCE_TYPES = ("Task", "Test Case")


def _derive_criteria_from_tasks(session: Session, synced: list[tuple[Any, dict[str, Any]]]) -> int:
    """For stories with no AC field, derive criteria from their child work items
    (Task / Test Case titles)."""
    by_parent: dict[int, list[str]] = {}
    for _row, model in synced:
        parent = model.get("parent_azure_id")
        if model["type"] in _CRITERIA_SOURCE_TYPES and parent is not None and model["title"]:
            by_parent.setdefault(parent, []).append(model["title"])
    added = 0
    for row, model in synced:
        if model["type"] != settings.azure_story_type:
            continue
        if az_repo.count_acceptance_criteria(session, row.id):
            continue
        titles = by_parent.get(model["azure_id"])
        if titles:
            az_repo.upsert_acceptance_criteria(session, row.id, titles[:30])
            added += 1
    return added


async def sync_pull_requests(session: Session, client: AzureClientBase) -> int:
    raw = await client.list_pull_requests()
    now = datetime.now(timezone.utc)
    count = 0
    for item in raw[:500]:
        count += 1
        az_repo.upsert_pull_request(
            session,
            {
                "azure_id": int(item["pullRequestId"]),
                "title": item.get("title", ""),
                "repo": (item.get("repository") or {}).get("name", ""),
                "source_ref": (item.get("sourceRefName") or "").replace("refs/heads/", ""),
                "target_ref": (item.get("targetRefName") or "").replace("refs/heads/", ""),
                "status": item.get("status", ""),
                "author": (item.get("createdBy") or {}).get("displayName", ""),
                "created_at": _parse_dt(item.get("creationDate")),
                "updated_at": _parse_dt(item.get("creationDate")),
                "closed_at": _parse_dt(item.get("closedDate")),
                "commit_count": item.get("commitIds", []).__len__() if isinstance(item.get("commitIds"), list) else 0,
                "url": item.get("url", ""),
                "last_synced_at": now,
            },
        )
    return count


async def sync_all(session: Session, client: AzureClientBase) -> dict[str, int]:
    iterations = await sync_iterations(session, client)
    work_items = await sync_work_items(session, client)
    prs = await sync_pull_requests(session, client)
    session.commit()
    return {"iterations": iterations, "work_items": work_items, "pull_requests": prs}


def _log_sync(session: Session, kind: str, *, started_at: datetime, upserted: int,
              status: str, error: str | None = None) -> None:
    log = AzureSyncLog(
        kind=kind, started_at=started_at, completed_at=datetime.now(timezone.utc),
        upserted=upserted, status=status, error=error,
    )
    session.add(log)
