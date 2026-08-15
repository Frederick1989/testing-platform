"""Azure DevOps synchronization workflows (idempotent)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.azure.client import AzureClientBase, strip_html
from app.models.azure import AzureSyncLog
from app.repositories import azure as az_repo

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
        "acceptance_criteria_raw": strip_html(
            fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "") or ""
        ),
        "state": fields.get("System.State", ""),
        "assigned_to": assigned_name,
        "iteration_name": fields.get("System.IterationPath", "").split("\\")[-1],
        "area_path": fields.get("System.AreaPath", ""),
        "created_at": _parse_dt(fields.get("System.CreatedDate")),
        "updated_at": _parse_dt(fields.get("System.ChangedDate")),
        "closed_at": _parse_dt(fields.get("System.ClosedDate")),
        "tags": tags,
        "url": fields.get("System.Url", ""),
        "parent_azure_id": fields.get("System.Parent"),
        "comment_count": int(fields.get("System.CommentCount") or 0),
        "last_synced_at": now,
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
        # name of the "Current" iteration should be its path leaf, but that is a
        # team-level concept; store the resolved leaf if possible.
        is_current = bool(current_path and item.get("path") == current_path)
        az_repo.upsert_iteration(
            session,
            {
                "azure_id": azure_id,
                "name": name,
                "path": item.get("path", ""),
                "state": item.get("attributes", {}).get("timeFrame", "")
                if isinstance(item.get("attributes"), dict) else "",
                "start_date": _parse_dt(item.get("attributes", {}).get("startDate"))
                if isinstance(item.get("attributes"), dict) else None,
                "finish_date": _parse_dt(item.get("attributes", {}).get("finishDate"))
                if isinstance(item.get("attributes"), dict) else None,
                "is_current": is_current,
                "url": item.get("url", ""),
                "last_synced_at": now,
            },
        )
        count += 1
    return count


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
    count = 0
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
        count += 1
    return count


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
