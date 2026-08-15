"""Risk computation — deterministic, from persisted data."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.azure import WorkItem
from app.models.test import (
    AcceptanceCriterion,
    Defect,
    TestResult,
    TestStoryLink,
)


def compute_risks(session: Session) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []

    # 1. uncovered acceptance criteria
    uncovered = session.scalars(
        select(AcceptanceCriterion).where(
            AcceptanceCriterion.is_active.is_(True),
            AcceptanceCriterion.status.in_(["NOT_COVERED", "PARTIALLY_COVERED"]),
        )
    ).all()
    if uncovered:
        stories = {wi.azure_id: wi.title for wi in session.scalars(select(WorkItem))}
        risks.append(
            {
                "category": "coverage",
                "severity": "HIGH",
                "title": f"{len(uncovered)} acceptance criteria without full test coverage",
                "description": "Requirements are at risk of untested behaviour.",
                "count": len(uncovered),
                "items": [
                    {
                        "work_item_id": u.work_item_id,
                        "story": stories.get(u.work_item_id, "?"),
                        "criterion": u.text[:120],
                    }
                    for u in uncovered[:20]
                ],
            }
        )

    # 2. failing tests
    failed = session.scalars(
        select(TestResult).where(TestResult.status.in_(["FAILED", "ERROR"]))
    ).all()
    if failed:
        risks.append(
            {
                "category": "execution",
                "severity": "HIGH",
                "title": f"{len(failed)} failed test results",
                "description": "Failing automated tests block confidence in delivery.",
                "count": len(failed),
                "items": [{"id": f.id, "title": f.title[:120]} for f in failed[:20]],
            }
        )

    # 3. blocking defects
    blockers = session.scalars(
        select(Defect).where(
            Defect.state.notin_(["Closed", "Resolved", "Removed"]),
            Defect.severity.in_(["CRITICAL", "HIGH"]),
        )
    ).all()
    if blockers:
        risks.append(
            {
                "category": "defects",
                "severity": "CRITICAL",
                "title": f"{len(blockers)} blocking defects open",
                "description": "Critical/high severity defects are unresolved.",
                "count": len(blockers),
                "items": [{"id": b.id, "azure_id": b.azure_id, "title": b.title[:120]} for b in blockers[:20]],
            }
        )

    # 4. stories without execution
    stories = session.scalars(
        select(WorkItem).where(WorkItem.type == settings.azure_story_type, WorkItem.is_active.is_(True))
    ).all()
    unexecuted = []
    for story in stories:
        linked = session.scalar(
            select(func.count(TestStoryLink.id)).where(
                TestStoryLink.work_item_id == story.id
            )
        )
        if not linked:
            unexecuted.append(story)
    if unexecuted:
        risks.append(
            {
                "category": "execution",
                "severity": "MEDIUM",
                "title": f"{len(unexecuted)} stories have no linked tests",
                "description": "These stories have not been exercised by automation.",
                "count": len(unexecuted),
                "items": [{"azure_id": s.azure_id, "title": s.title[:120]} for s in unexecuted[:20]],
            }
        )

    risks.sort(key=lambda r: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[r["severity"]])
    return risks
