"""UAT readiness — deterministic scoring model."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.azure import WorkItem
from app.config import settings
from app.models.test import Defect, TestResult, TestStoryLink


def evaluate_story(session: Session, work_item_pk: int, *,
                   execution_window_days: int = 14) -> dict[str, Any]:
    story = session.get(WorkItem, work_item_pk)
    if story is None:
        raise ValueError("story not found")

    acs = [ac for ac in story.acceptance_criteria if ac.is_active]
    ac_statuses = [ac.status for ac in acs]
    ac_covered = sum(1 for s in ac_statuses if s in ("COVERED", "PARTIALLY_COVERED"))

    # latest results for linked test cases
    link_ids = [
        link.test_case_id for link in session.scalars(
            select(TestStoryLink).where(TestStoryLink.work_item_id == story.id)
        )
    ]
    latest_results: dict[int, TestResult] = {}
    for tc_id in link_ids:
        res = session.scalar(
            select(TestResult)
            .where(TestResult.test_case_id == tc_id)
            .order_by(TestResult.started_at.desc())
            .limit(1)
        )
        if res:
            latest_results[tc_id] = res

    blocking_defects = list(
        session.scalars(
            select(Defect).where(
                Defect.story_work_item_id == story.azure_id,
                Defect.state.notin_(["Closed", "Resolved", "Removed"]),
                Defect.severity.in_(["CRITICAL", "HIGH"]),
            )
        )
    )

    open_defects = list(
        session.scalars(
            select(Defect).where(
                Defect.story_work_item_id == story.azure_id,
                Defect.state.notin_(["Closed", "Resolved", "Removed"]),
            )
        )
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=execution_window_days)
    recent_executed = any(
        r.started_at and r.started_at >= cutoff and r.status != "SKIPPED"
        for r in latest_results.values()
    )
    latest_ok = latest_results and all(
        r.status in ("PASSED", "FLAKY", "SKIPPED") for r in latest_results.values()
    )

    gates = {
        "all_acceptance_criteria_covered": bool(acs) and ac_covered == len(acs),
        "linked_tests_exist": bool(link_ids),
        "latest_execution_successful": latest_ok,
        "recently_executed": recent_executed,
        "no_blocking_defects": not blocking_defects,
        "no_open_defects": not open_defects,
    }
    ready = all(gates.values())
    return {
        "work_item_id": work_item_pk,
        "ready": ready,
        "gates": gates,
        "acceptance_criteria": ac_statuses,
        "acceptance_criteria_covered": ac_covered,
        "acceptance_criteria_total": len(acs),
        "blocking_defects": [d.title for d in blocking_defects],
        "open_defects": len(open_defects),
        "latest_results": {k: v.status for k, v in latest_results.items()},
        "evaluated_at": datetime.now(timezone.utc),
    }


def list_ready_stories(session: Session) -> list[dict[str, Any]]:
    stories = session.scalars(
        select(WorkItem)
        .where(WorkItem.type == settings.azure_story_type, WorkItem.is_active.is_(True))
        .order_by(WorkItem.azure_id)
    )
    ready: list[dict[str, Any]] = []
    for story in stories:
        try:
            evaluation = evaluate_story(session, story.id)
        except ValueError:
            continue
        if evaluation["ready"]:
            ready.append(
                {
                    "id": story.id,
                    "azure_id": story.azure_id,
                    "title": story.title,
                    "url": story.url,
                    "iteration_name": story.iteration_name,
                    "status": "UAT_READY",
                }
            )
    return ready
