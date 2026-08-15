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
        "defect_trend": defects_svc.trend(session, days=30),
        "generated_at": datetime.now(timezone.utc),
    }


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
