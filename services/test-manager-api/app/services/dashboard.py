"""Dashboard aggregation endpoint — a single payload for the UAT dashboard."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import azure as az_repo
from app.services import coverage as coverage_svc
from app.services import defects as defects_svc
from app.services import flakiness as flakiness_svc
from app.services import risks as risks_svc
from app.services import sprints as sprints_svc
from app.services.readiness import list_ready_stories


def summary(session: Session) -> dict[str, Any]:
    current = az_repo.get_current_iteration(session)
    sprint = sprints_svc.sprint_metrics(session, current)
    coverage = coverage_svc.summarize(session)
    defects = defects_svc.summary(session)
    health = flakiness_svc.test_health_stats(session)
    flaky = flakiness_svc.flaky_tests(session)
    regression = flakiness_svc.regression_report(session)
    risks = risks_svc.compute_risks(session)
    ready = list_ready_stories(session)
    resolution = defects_svc.resolution_distribution(session)
    aging = defects_svc.open_aging(session)
    capacity = coverage_svc.capacity_split(session)
    missing_ac = coverage_svc.automated_stories_missing_ac(session)

    runs = _recent_runs(session)
    return {
        "current_sprint": current.name if current else None,
        "sprint": sprint,
        "coverage": coverage,
        "defects": defects,
        "test_health": health,
        "flaky": flaky["count"],
        "flaky_tests": flaky["tests"][:20],
        "regression": regression,
        "risks": risks,
        "ready_stories": ready,
        "recent_runs": runs,
        "velocity": sprints_svc.velocity_series(session),
        "defect_resolution": resolution,
        "open_defect_aging": aging,
        "capacity": capacity,
        "missing_ac_stories": missing_ac,
        "pain_points": _pain_points(
            defects=defects, health=health, resolution=resolution,
            aging=aging, capacity=capacity, missing_ac=missing_ac,
            coverage=coverage,
        ),
        "generated_at": datetime.now(timezone.utc),
    }


def _pain_points(
    *,
    defects: dict[str, Any],
    health: dict[str, Any],
    resolution: dict[str, Any],
    aging: dict[str, Any],
    capacity: dict[str, Any],
    missing_ac: dict[str, Any],
    coverage: dict[str, Any],
) -> list[dict[str, str]]:
    """Executive-focused findings: what is slowing go-live and where the
    bottleneck actually sits (defect resolution, not test execution)."""
    points: list[dict[str, str]] = []

    mttr = resolution["stats"].get("avg_hours")
    if resolution["count"]:
        if mttr is not None and mttr > 168:
            points.append({
                "level": "critical",
                "title": "Defects take more than a week to resolve",
                "detail": (
                    f"Average time to resolve is {mttr:.0f}h "
                    f"({mttr / 24:.1f} days); {resolution['over_7d_pct']}% of resolved "
                    f"defects exceeded 7 days. Testing finds issues quickly — "
                    f"resolution is the bottleneck."
                ),
            })
        elif mttr is not None and mttr > 72:
            points.append({
                "level": "warning",
                "title": "Defect resolution is slower than target",
                "detail": (
                    f"Average time to resolve is {mttr:.0f}h ({mttr / 24:.1f} days) "
                    f"against a 3-day target; {resolution['over_7d_pct']}% of resolved "
                    f"defects exceeded 7 days."
                ),
            })

    if aging["open"] and aging["over_7d"]:
        points.append({
            "level": "warning" if aging["over_7d"] <= 3 else "critical",
            "title": f"{aging['over_7d']} of {aging['open']} open defects are older than a week",
            "detail": (
                f"{aging['over_7d_pct']}% of open defects are aging beyond 7 days. "
                + (f"Oldest: {aging['oldest']['title']} (opened {aging['oldest']['days']}d ago)."
                   if aging["oldest"] else "")
            ),
        })

    if defects.get("blockers"):
        points.append({
            "level": "critical",
            "title": f"{defects['blockers']} high/critical defects are open",
            "detail": f"{defects.get('critical', 0)} critical — these block release sign-off.",
        })

    if missing_ac["count"]:
        points.append({
            "level": "warning",
            "title": f"{missing_ac['count']} automated stories have no acceptance criteria",
            "detail": "Automation coverage cannot be measured until AC (or linked tests) are added.",
        })

    if capacity["total"] and capacity["automated_pct"] < 40:
        points.append({
            "level": "info",
            "title": "Manual effort dominates the test backlog",
            "detail": (
                f"{capacity['manual_pct']}% of stories are manual effort vs "
                f"{capacity['automated_pct']}% automated. Automation is the growth lever "
                f"for release speed."
            ),
        })

    pass_rate = health.get("pass_rate")
    if pass_rate is not None and pass_rate >= 90 and not any(
        p["level"] == "critical" for p in points
    ):
        points.append({
            "level": "info",
            "title": "Test execution is healthy and fast",
            "detail": (
                f"{pass_rate}% pass rate across {health.get('total', 0)} tests — "
                f"UAT is not the bottleneck; defects waiting on development are."
            ),
        })
    if not points:
        points.append({
            "level": "info",
            "title": "No critical pain points detected",
            "detail": "Metrics are within target ranges.",
        })
    return points


def _recent_runs(session: Session, limit: int = 20) -> list[dict[str, Any]]:
    from app.repositories import tests as test_repo

    runs = test_repo.list_test_runs(session, limit=limit)
    return [
        {
            "run_id": r.run_id,
            "framework": r.framework,
            "environment": r.environment,
            "branch": r.branch,
            "status": r.status,
            "total": r.total,
            "passed": r.passed,
            "failed": r.failed,
            "skipped": r.skipped,
            "flaky": r.flaky,
            "created_at": r.created_at,
        }
        for r in runs
    ]
