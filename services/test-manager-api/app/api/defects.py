"""Defects router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db
from app.core.auth import require_token
from app.core.errors import NotFoundError
from app.repositories import tests as test_repo
from app.services import defects as defects_svc

router = APIRouter(
    prefix="/defects", tags=["defects"], dependencies=[Depends(require_token)]
)


@router.get("")
def list_defects(
    session: Annotated[Session, Depends(db)],
    state: str | None = None,
    severity: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    items, total = test_repo.list_defects(
        session, state=state, severity=severity, page=page, page_size=page_size
    )
    return {
        "items": [
            {
                "id": d.id, "azure_id": d.azure_id, "title": d.title,
                "description": d.description, "severity": d.severity,
                "priority": d.priority, "state": d.state,
                "assigned_to": d.assigned_to, "story_work_item_id": d.story_work_item_id,
                "created_at": d.created_at, "resolved_at": d.resolved_at,
                "closed_at": d.closed_at, "reopened_count": d.reopened_count,
                "url": d.url, "iteration_name": d.iteration_name,
            }
            for d in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/summary")
def defects_summary(session: Annotated[Session, Depends(db)]) -> dict:
    return defects_svc.summary(session)


@router.get("/trend")
def defects_trend(session: Annotated[Session, Depends(db)], days: int = 30) -> dict:
    return {"items": defects_svc.trend(session, days=days)}


@router.get("/resolution-times")
def resolution_times(session: Annotated[Session, Depends(db)]) -> dict:
    return defects_svc.resolution_times(session)


@router.get("/{defect_id}")
def get_defect(
    defect_id: int,
    session: Annotated[Session, Depends(db)],
) -> dict:
    d = test_repo.get_defect(session, defect_id)
    if d is None:
        raise NotFoundError(f"defect {defect_id} not found")
    links = test_repo.list_defect_links_for_defect(session, defect_id)
    return {
        "id": d.id, "azure_id": d.azure_id, "title": d.title,
        "description": d.description, "severity": d.severity,
        "state": d.state, "assigned_to": d.assigned_to,
        "created_at": d.created_at, "resolved_at": d.resolved_at,
        "closed_at": d.closed_at, "reopened_count": d.reopened_count,
        "url": d.url, "story_work_item_id": d.story_work_item_id,
        "links": [
            {"id": link.id, "test_result_id": link.test_result_id,
             "test_case_id": link.test_case_id, "reason": link.reason}
            for link in links
        ],
    }
