"""Test matrix router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db
from app.core.errors import NotFoundError
from app.services import matrix as matrix_svc

router = APIRouter(prefix="/test-matrix", tags=["test-matrix"])


@router.get("/{work_item_id}")
def get_matrix(
    work_item_id: int,
    session: Annotated[Session, Depends(db)],
) -> dict:
    from app.repositories import azure as az_repo

    story = az_repo.resolve_work_item(session, work_item_id)
    if story is None:
        raise NotFoundError(f"work item {work_item_id} not found")
    return matrix_svc.build_matrix(session, story.id)


@router.get("")
def list_matrix(
    session: Annotated[Session, Depends(db)],
    iteration: str | None = None,
) -> dict:
    rows = matrix_svc.matrix_for_sprint(session, iteration)
    return {"items": rows, "total": len(rows)}
