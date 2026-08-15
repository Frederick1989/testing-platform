"""Coverage metrics — deterministic calculations from persisted data.

Coverage is not code coverage: it measures requirements (AC), stories,
automation and execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.azure import WorkItem
from app.models.test import (
    AcceptanceCriterion,
    TestCase,
    TestImplementation,
    TestResult,
    TestRun,
    TestStoryLink,
)


@dataclass
class CoverageSummary:
    requirement: float
    story: float
    automation: float
    execution: float
    acceptance_criteria_total: int
    acceptance_criteria_covered: int
    stories_total: int
    stories_covered: int
    test_cases_total: int
    test_cases_automated: int
    active_tests: int
    executed_tests: int
    latest_run: datetime | None


def _stories(session: Session) -> list[WorkItem]:
    rows = session.scalars(
        select(WorkItem)
        .where(WorkItem.type == settings.azure_story_type, WorkItem.is_active.is_(True))
    )
    # non-test effort (Acceptance Test Required = False) is excluded from coverage
    from app.repositories import azure as az_repo

    return [w for w in rows if az_repo.acceptance_test_required(w)]


def capacity_split(session: Session) -> dict[str, Any]:
    """Automation vs manual test-effort split, measured as story counts.

    Stories with 'Acceptance Test Required' = False (e.g. environment setup)
    are reported separately as 'non_test'. Empty/absent automation status
    counts as manual effort.
    """
    from app.repositories import azure as az_repo

    rows = session.scalars(
        select(WorkItem)
        .where(WorkItem.type == settings.azure_story_type, WorkItem.is_active.is_(True))
    )
    automated = 0
    manual = 0
    non_test = 0
    for story in rows:
        if not az_repo.acceptance_test_required(story):
            non_test += 1
        elif az_repo.automation_status(story) == "automated":
            automated += 1
        else:
            manual += 1
    total = automated + manual + non_test
    return {
        "automated": automated,
        "manual": manual,
        "non_test": non_test,
        "total": total,
        "automated_pct": round(automated / total * 100, 1) if total else 0.0,
        "manual_pct": round(manual / total * 100, 1) if total else 0.0,
        "non_test_pct": round(non_test / total * 100, 1) if total else 0.0,
    }


def automated_stories_missing_ac(session: Session) -> dict[str, Any]:
    """Stories flagged as automated but with no acceptance criteria attached —
    a validation gap that blocks automation coverage from being measured."""
    from app.repositories import azure as az_repo

    rows = session.scalars(
        select(WorkItem)
        .where(WorkItem.type == settings.azure_story_type, WorkItem.is_active.is_(True))
    )
    missing: list[dict[str, Any]] = []
    for story in rows:
        if not az_repo.acceptance_test_required(story):
            continue
        if az_repo.automation_status(story) != "automated":
            continue
        active_acs = [ac for ac in story.acceptance_criteria if ac.is_active]
        if not active_acs:
            missing.append({"id": story.id, "azure_id": story.azure_id, "title": story.title})
    return {"count": len(missing), "items": missing[:10]}


def acceptance_criteria_coverage(session: Session) -> dict[str, Any]:
    total = session.scalar(
        select(func.count(AcceptanceCriterion.id)).where(
            AcceptanceCriterion.is_active.is_(True)
        )
    )
    covered = session.scalar(
        select(func.count(AcceptanceCriterion.id)).where(
            AcceptanceCriterion.is_active.is_(True),
            AcceptanceCriterion.status.in_(["COVERED", "PARTIALLY_COVERED"]),
        )
    )
    total = total or 0
    covered = covered or 0
    return {
        "total": total,
        "covered": covered,
        "coverage": round(covered / total * 100, 1) if total else 0.0,
    }


def story_coverage(session: Session) -> dict[str, Any]:
    stories = _stories(session)
    total = len(stories)
    covered = 0
    for story in stories:
        acs = [ac for ac in story.acceptance_criteria if ac.is_active]
        if not acs:
            continue
        if all(ac.status == "COVERED" for ac in acs):
            covered += 1
    return {
        "total": total,
        "covered": covered,
        "coverage": round(covered / total * 100, 1) if total else 0.0,
    }


def automation_coverage(session: Session) -> dict[str, Any]:
    total = session.scalar(select(func.count(TestCase.id)).where(TestCase.status == "active")) or 0
    automated = session.scalar(
        select(func.count(func.distinct(TestCase.id)))
        .select_from(TestCase)
        .join(TestImplementation, TestImplementation.test_case_id == TestCase.id)
        .where(TestCase.status == "active")
    ) or 0
    return {
        "total": total,
        "automated": automated,
        "coverage": round(automated / total * 100, 1) if total else 0.0,
    }


def execution_coverage(session: Session, days: int = 30) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    active = session.scalar(
        select(func.count(func.distinct(TestResult.test_case_id))).where(
            TestResult.started_at >= cutoff,
            TestResult.status != "SKIPPED",
        )
    ) or 0
    total = session.scalar(select(func.count(TestCase.id)).where(TestCase.status == "active")) or 0
    return {
        "total": total,
        "executed": active,
        "coverage": round(active / total * 100, 1) if total else 0.0,
        "window_days": days,
    }


def summarize(session: Session, *, execution_days: int = 30) -> dict[str, Any]:
    ac = acceptance_criteria_coverage(session)
    story = story_coverage(session)
    automation = automation_coverage(session)
    execution = execution_coverage(session, days=execution_days)
    latest_run = session.scalar(select(func.max(TestRun.started_at)))
    return {
        "requirement": ac["coverage"],
        "story": story["coverage"],
        "automation": automation["coverage"],
        "execution": execution["coverage"],
        "acceptance_criteria_total": ac["total"],
        "acceptance_criteria_covered": ac["covered"],
        "stories_total": story["total"],
        "stories_covered": story["covered"],
        "test_cases_total": automation["total"],
        "test_cases_automated": automation["automated"],
        "executed_tests": execution["executed"],
        "latest_run": latest_run,
        "execution_window_days": execution_days,
    }


def coverage_gaps(session: Session) -> dict[str, Any]:
    """AC without tests, stories without execution, stories with any gap."""
    uncovered_ac: list[dict[str, Any]] = []
    for ac in session.scalars(
        select(AcceptanceCriterion).where(AcceptanceCriterion.is_active.is_(True))
    ):
        if ac.status in ("NOT_COVERED", "PARTIALLY_COVERED"):
            uncovered_ac.append(
                {
                    "id": ac.id,
                    "work_item_id": ac.work_item_id,
                    "text": ac.text,
                    "status": ac.status,
                }
            )
    unexecuted_stories: list[dict[str, Any]] = []
    for story in _stories(session):
        executed = session.scalar(
            select(func.count(TestResult.id))
            .select_from(TestResult)
            .join(TestStoryLink, TestStoryLink.test_case_id == TestResult.test_case_id)
            .where(TestStoryLink.work_item_id == story.id)
        )
        if not executed:
            unexecuted_stories.append(
                {"id": story.id, "azure_id": story.azure_id, "title": story.title,
                 "state": story.state}
            )
    return {
        "uncovered_acceptance_criteria": uncovered_ac[:100],
        "unexecuted_stories": unexecuted_stories[:100],
        "counts": {
            "uncovered_ac": len(uncovered_ac),
            "unexecuted_stories": len(unexecuted_stories),
        },
    }
