"""Defect intelligence metrics."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.test import Defect

_OPEN_STATES = ("New", "Active", "Approved")
_CLOSED_STATES = ("Closed", "Resolved", "Removed")


def summary(session: Session) -> dict[str, Any]:
    all_defects = session.scalars(select(Defect)).all()
    now = datetime.now(timezone.utc)

    total = len(all_defects)
    open_defects = [d for d in all_defects if d.state in _OPEN_STATES]
    resolved = [d for d in all_defects if d.state in _CLOSED_STATES]
    critical = [d for d in open_defects if d.severity == "CRITICAL"]
    blockers = [d for d in open_defects if d.severity in ("CRITICAL", "HIGH")]
    reopened = [d for d in all_defects if d.reopened_count and d.reopened_count > 0]

    mttr_hours = None
    for d in resolved:
        if d.created_at and d.resolved_at:
            h = (d.resolved_at - d.created_at).total_seconds() / 3600
            mttr_hours = h if mttr_hours is None else (mttr_hours + h)
    if mttr_hours is not None and resolved:
        mttr_hours = round(mttr_hours / len(resolved), 1)

    aging_days = None
    oldest = None
    for d in open_defects:
        if d.created_at:
            days = (now - d.created_at).total_seconds() / 86400
            if aging_days is None or days > aging_days:
                aging_days = round(days, 1)
                oldest = {"id": d.id, "azure_id": d.azure_id, "title": d.title,
                          "age_days": aging_days, "severity": d.severity}

    by_severity: dict[str, int] = {}
    for d in open_defects:
        by_severity[d.severity] = by_severity.get(d.severity, 0) + 1

    by_state: dict[str, int] = {}
    for d in all_defects:
        by_state[d.state] = by_state.get(d.state, 0) + 1

    return {
        "total": total,
        "open": len(open_defects),
        "resolved": len(resolved),
        "critical": len(critical),
        "blockers": len(blockers),
        "reopened": len(reopened),
        "mttr_hours": mttr_hours,
        "oldest_open": oldest,
        "aging_days_avg": round(
            sum(((now - d.created_at).total_seconds() / 86400) for d in open_defects if d.created_at)
            / max(len([d for d in open_defects if d.created_at]), 1),
            1,
        ),
        "by_severity": by_severity,
        "by_state": by_state,
        "reopen_rate": round(len(reopened) / max(total, 1) * 100, 1),
        "defect_density": round(len(all_defects) / max(_story_count(session), 1), 2),
    }


def _story_count(session: Session) -> int:
    from app.models.azure import WorkItem

    return session.scalar(
        select(func.count(WorkItem.id)).where(WorkItem.type == settings.azure_story_type)
    ) or 0


def trend(session: Session, days: int = 30) -> list[dict[str, Any]]:
    from collections import defaultdict
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    opened: dict[str, int] = defaultdict(int)
    closed: dict[str, int] = defaultdict(int)
    for d in session.scalars(select(Defect)):
        if d.created_at and d.created_at >= start:
            opened[d.created_at.date().isoformat()] += 1
        if d.closed_at and d.closed_at >= start:
            closed[d.closed_at.date().isoformat()] += 1
    result = []
    for i in range(days + 1):
        day = (start + timedelta(days=i)).date().isoformat()
        result.append({"date": day, "opened": opened.get(day, 0), "closed": closed.get(day, 0)})
    return result


def resolution_times(session: Session) -> dict[str, Any]:
    resolved = [d for d in session.scalars(select(Defect)) if d.state in _CLOSED_STATES]
    hours = []
    for d in resolved:
        if d.created_at and d.resolved_at:
            hours.append(round((d.resolved_at - d.created_at).total_seconds() / 3600, 1))
    if not hours:
        return {"count": 0, "avg_hours": None, "p50_hours": None, "p95_hours": None}
    hours.sort()
    return {
        "count": len(hours),
        "avg_hours": round(sum(hours) / len(hours), 1),
        "p50_hours": hours[len(hours) // 2],
        "p95_hours": hours[int(len(hours) * 0.95) - 1] if len(hours) > 1 else hours[-1],
    }
