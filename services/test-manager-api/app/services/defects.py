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
    import math

    def pct(idx_frac: float) -> float:
        return hours[min(len(hours) - 1, max(0, int(math.ceil(len(hours) * idx_frac)) - 1))]

    return {
        "count": len(hours),
        "avg_hours": round(sum(hours) / len(hours), 1),
        "p50_hours": pct(0.5),
        "p95_hours": pct(0.95),
    }


_RESOLUTION_BUCKETS = (
    ("< 1 day", 0, 24),
    ("1 - 3 days", 24, 72),
    ("3 - 7 days", 72, 168),
    ("7 - 14 days", 168, 336),
    ("14 - 30 days", 336, 720),
    ("> 30 days", 720, None),
)


def resolution_distribution(session: Session) -> dict[str, Any]:
    """How long defects take to be resolved — the distribution plus aggregate
    stats. Highlights the pain point when defects wait on development."""
    resolved = [d for d in session.scalars(select(Defect)) if d.state in _CLOSED_STATES]
    buckets = [{"label": label, "min_hours": lo, "count": 0} for label, lo, _ in _RESOLUTION_BUCKETS]
    hours: list[float] = []
    slowest: list[dict[str, Any]] = []
    for d in resolved:
        if not (d.created_at and d.resolved_at):
            continue
        h = (d.resolved_at - d.created_at).total_seconds() / 3600
        hours.append(h)
        for bucket in buckets:
            lo = bucket["min_hours"]
            hi = next((b[2] for b in _RESOLUTION_BUCKETS if b[0] == bucket["label"]), None)
            if (hi is None or h < hi) and h >= lo:
                bucket["count"] += 1
                break
        if len(slowest) < 5 or h > slowest[-1]["hours"]:
            slowest.append(
                {"azure_id": d.azure_id, "title": d.title[:120],
                 "hours": round(h, 1), "days": round(h / 24, 1),
                 "assigned_to": d.assigned_to, "state": d.state}
            )
            slowest.sort(key=lambda x: x["hours"], reverse=True)
            slowest = slowest[:5]
    stats = resolution_times(session)
    return {
        "count": len(hours),
        "distribution": buckets,
        "stats": stats,
        "slowest": slowest,
        "over_7d_pct": round(
            sum(1 for h in hours if h >= 168) / max(len(hours), 1) * 100, 1
        ),
    }


def open_aging(session: Session) -> dict[str, Any]:
    """Age of currently open defects — the 'waiting on dev' signal."""
    now = datetime.now(timezone.utc)
    open_defects = [d for d in session.scalars(select(Defect)) if d.state in _OPEN_STATES]
    buckets = [
        {"label": "< 1 week", "count": 0},
        {"label": "1 - 2 weeks", "count": 0},
        {"label": "2 - 4 weeks", "count": 0},
        {"label": "> 1 month", "count": 0},
    ]
    oldest: dict[str, Any] | None = None
    for d in open_defects:
        if not d.created_at:
            continue
        days = (now - d.created_at).total_seconds() / 86400
        idx = 0 if days < 7 else 1 if days < 14 else 2 if days < 30 else 3
        buckets[idx]["count"] += 1
        if oldest is None or days > oldest["days"]:
            oldest = {
                "azure_id": d.azure_id, "title": d.title[:120], "days": round(days, 1),
                "severity": d.severity, "assigned_to": d.assigned_to,
            }
    return {
        "open": len(open_defects),
        "buckets": buckets,
        "oldest": oldest,
        "over_7d": sum(b["count"] for b in buckets[1:]),
        "over_7d_pct": round(
            sum(b["count"] for b in buckets[1:]) / max(len(open_defects), 1) * 100, 1
        ),
    }
