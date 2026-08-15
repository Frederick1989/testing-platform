"""Test-manager router: analysis and test generation."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db
from app.core.auth import require_token
from app.core.types import JobType
from app.schemas.intelligence import (
    CreateTestCasesRequest,
    SyncTestMatrixRequest,
)

router = APIRouter(prefix="/test-manager", tags=["test-manager"])


@router.post("/sync-test-matrix", status_code=202)
async def sync_test_matrix(
    body: SyncTestMatrixRequest,
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    from app.core.errors import NotFoundError
    from app.jobs.scheduler import enqueue_job
    from app.repositories import azure as az_repo

    story = az_repo.resolve_work_item(session, body.work_item_id)
    if story is None:
        raise NotFoundError(f"work item {body.work_item_id} not found")
    job_id = enqueue_job(
        JobType.TEST_MATRIX_ANALYSIS,
        {"work_item_id": story.id, "force": body.force},
        trigger="manual",
    )
    return {"job_id": job_id, "status": "QUEUED"}


@router.post("/create-test-cases", status_code=202)
async def create_test_cases(
    body: CreateTestCasesRequest,
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    from app.core.errors import NotFoundError
    from app.jobs.scheduler import enqueue_job
    from app.repositories import azure as az_repo

    story = az_repo.resolve_work_item(session, body.work_item_id)
    if story is None:
        raise NotFoundError(f"work item {body.work_item_id} not found")
    job_id = enqueue_job(
        JobType.TEST_GENERATION,
        {"work_item_id": story.id},
        trigger="manual",
    )
    return {"job_id": job_id, "status": "QUEUED"}


@router.get("/analyses/{work_item_id}")
def latest_analysis(
    work_item_id: int,
    session: Annotated[Session, Depends(db)],
) -> dict:
    from sqlalchemy import select

    from app.models.analysis import TestMatrixAnalysis

    row = session.scalar(
        select(TestMatrixAnalysis)
        .where(TestMatrixAnalysis.work_item_id == work_item_id)
        .order_by(TestMatrixAnalysis.generated_at.desc())
        .limit(1)
    )
    if row is None:
        from app.core.errors import NotFoundError

        raise NotFoundError(f"no analysis for work item {work_item_id}")
    return {
        "analysis_id": row.id,
        "coverage": row.coverage_pct,
        "missing_acceptance_criteria": row.missing_ac_count,
        "existing_tests_reused": row.existing_tests_reused,
        "new_tests_required": row.new_tests_required,
        "potentially_redundant_tests": row.potentially_redundant_tests,
        "status": row.status,
        "details": row.details,
        "model": row.model,
        "generated_at": row.generated_at,
    }


@router.get("/stories/ready")
def ready_stories(session: Annotated[Session, Depends(db)]) -> dict:
    from app.services.readiness import list_ready_stories

    return {"items": list_ready_stories(session)}
