"""Coverage router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db
from app.config import settings
from app.core.auth import require_token
from app.services import coverage as coverage_svc

router = APIRouter(
    prefix="/coverage", tags=["coverage"], dependencies=[Depends(require_token)]
)


@router.get("/summary")
def coverage_summary(session: Annotated[Session, Depends(db)]) -> dict:
    return coverage_svc.summarize(session)


@router.get("/acceptance-criteria")
def acceptance_criteria(session: Annotated[Session, Depends(db)]) -> dict:
    from sqlalchemy import select

    from app.models.azure import WorkItem
    from app.models.test import AcceptanceCriterion

    rows = session.scalars(
        select(AcceptanceCriterion)
        .where(AcceptanceCriterion.is_active.is_(True))
        .order_by(AcceptanceCriterion.work_item_id, AcceptanceCriterion.sort_order)
    ).all()
    story_titles = {
        w.id: (w.azure_id, w.title)
        for w in session.scalars(select(WorkItem)).all()
    }
    return {
        "items": [
            {
                "id": a.id, "work_item_id": a.work_item_id,
                "story_azure_id": story_titles.get(a.work_item_id, (None, ""))[0],
                "story_title": story_titles.get(a.work_item_id, (None, ""))[1],
                "text": a.text, "status": a.status, "sort_order": a.sort_order,
            }
            for a in rows
        ],
        "total": len(rows),
    }


@router.get("/by-story")
def coverage_by_story(session: Annotated[Session, Depends(db)]) -> dict:
    from app.models.azure import WorkItem

    stories = session.scalars(
        select(WorkItem).where(
            WorkItem.type == settings.azure_story_type, WorkItem.is_active.is_(True)
        )
    ).all()
    result = []
    for s in stories:
        acs = [a for a in s.acceptance_criteria if a.is_active]
        covered = sum(1 for a in acs if a.status == "COVERED")
        result.append(
            {
                "work_item_id": s.id, "azure_id": s.azure_id, "title": s.title,
                "iteration": s.iteration_name, "state": s.state,
                "acceptance_criteria_total": len(acs),
                "acceptance_criteria_covered": covered,
                "coverage": round(covered / max(len(acs), 1) * 100, 1),
                "status": "COVERED" if acs and covered == len(acs)
                else ("NOT_COVERED" if not acs else "PARTIALLY_COVERED"),
            }
        )
    return {"items": result}


@router.get("/gaps")
def coverage_gaps(session: Annotated[Session, Depends(db)]) -> dict:
    return coverage_svc.coverage_gaps(session)
