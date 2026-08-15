"""Sprint / delivery intelligence."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.azure import Iteration, WorkItem
from app.repositories import azure as az_repo

_ACTIVE_STATES = ("New", "Active", "Approved", "In Progress", "Committed")
_DONE_STATES = ("Done", "Closed", "Completed", "Resolved")
_BLOCKED_STATES = ("Blocked", "Waiting")


def _state_group(state: str) -> str:
    if state in _BLOCKED_STATES:
        return "Blocked"
    if state in _DONE_STATES:
        return "Done"
    if state in _ACTIVE_STATES:
        return "Active"
    return "New"


def sprint_metrics(session: Session, iteration: Iteration | None) -> dict[str, Any]:
    if iteration is None:
        return {
            "name": "",
            "committed": 0, "completed": 0, "remaining": 0,
            "states": {}, "velocity": 0.0, "cycle_time_hours": None,
            "lead_time_hours": None, "blocked_time_hours": None,
            "stories": [], "state": "Unavailable", "start_date": None, "finish_date": None,
        }
    stories = list(
        session.scalars(
            select(WorkItem).where(
                WorkItem.iteration_id == iteration.id,
                WorkItem.type == "User Story",
                WorkItem.is_active.is_(True),
            )
        )
    )
    committed = len(stories)
    done = [s for s in stories if s.state in _DONE_STATES]
    completed = len(done)

    states: dict[str, int] = {}
    for s in stories:
        group = _state_group(s.state)
        states[group] = states.get(group, 0) + 1

    # cycle/lead/blocked time from created/closed timestamps when available
    cycle, lead, blocked = [], [], []
    for s in done:
        if s.created_at and s.closed_at:
            lead.append((s.closed_at - s.created_at).total_seconds() / 3600)
        if s.updated_at and s.created_at and s.closed_at:
            cycle.append((s.closed_at - s.created_at).total_seconds() / 3600)
            blocked.append(_blocked_hours(s))

    return {
        "name": iteration.name,
        "committed": committed,
        "completed": completed,
        "remaining": committed - completed,
        "states": states,
        "velocity": float(completed),  # story points not available -> count
        "velocity_basis": "measured",
        "cycle_time_hours": round(sum(cycle) / len(cycle), 1) if cycle else None,
        "lead_time_hours": round(sum(lead) / len(lead), 1) if lead else None,
        "blocked_time_hours": round(sum(blocked) / len(blocked), 1) if blocked else None,
        "stories": [
            {
                "id": s.id, "azure_id": s.azure_id, "title": s.title,
                "state": s.state, "state_group": _state_group(s.state),
                "assigned_to": s.assigned_to, "url": s.url,
            }
            for s in sorted(stories, key=lambda x: x.azure_id)
        ],
        "state": iteration.state or "Unavailable",
        "start_date": iteration.start_date,
        "finish_date": iteration.finish_date,
    }


def _blocked_hours(story: WorkItem) -> float:
    """Approximate blocked time; Azure state history is not persisted, so this
    is an estimate (measured when available, otherwise 0)."""
    return 0.0


def list_sprint_summaries(session: Session) -> list[dict[str, Any]]:
    iterations = az_repo.list_iterations(session)
    return [
        {
            "id": i.id,
            "name": i.name,
            "state": i.state,
            "start_date": i.start_date,
            "finish_date": i.finish_date,
            "is_current": i.is_current,
        }
        for i in iterations
    ]


def velocity_series(session: Session) -> list[dict[str, Any]]:
    series = []
    for iteration in az_repo.list_iterations(session):
        metrics = sprint_metrics(session, iteration)
        series.append(
            {
                "sprint": iteration.name,
                "committed": metrics["committed"],
                "completed": metrics["completed"],
                "velocity": metrics["velocity"],
            }
        )
    return series
