"""Azure DevOps router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db
from app.core.auth import require_token
from app.core.types import JobType
from app.repositories import azure as az_repo
from app.schemas.azure import PullRequestOut, WorkItemOut

router = APIRouter(prefix="/azure", tags=["azure"])


@router.post("/sync", status_code=202)
async def sync_all(
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    from app.jobs.scheduler import enqueue_job

    job_id = enqueue_job(JobType.AZURE_SYNC, {}, trigger="manual")
    return {"job_id": job_id, "status": "QUEUED"}


@router.post("/sync/work-items", status_code=202)
async def sync_work_items(
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
    types: str | None = None,
) -> dict:
    from app.jobs.scheduler import enqueue_job

    job_id = enqueue_job(
        JobType.AZURE_SYNC_WORK_ITEMS,
        {"types": [t.strip() for t in types.split(",")] if types else None},
        trigger="manual",
    )
    return {"job_id": job_id, "status": "QUEUED"}


@router.post("/sync/pull-requests", status_code=202)
async def sync_pull_requests(
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    from app.jobs.scheduler import enqueue_job

    job_id = enqueue_job(JobType.AZURE_SYNC_PR, {}, trigger="manual")
    return {"job_id": job_id, "status": "QUEUED"}


@router.post("/sync/iterations", status_code=202)
async def sync_iterations(
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    from app.jobs.scheduler import enqueue_job

    job_id = enqueue_job(JobType.AZURE_SYNC_ITERATIONS, {}, trigger="manual")
    return {"job_id": job_id, "status": "QUEUED"}


@router.get("/work-items/{work_item_id}", response_model=WorkItemOut)
def get_work_item(
    work_item_id: int,
    session: Annotated[Session, Depends(db)],
) -> WorkItemOut:
    row = az_repo.get_work_item_by_azure_id(session, work_item_id)
    if row is None:
        from app.core.errors import NotFoundError

        raise NotFoundError(f"work item {work_item_id} not found")
    return WorkItemOut.model_validate(row)


@router.get("/work-items")
def list_work_items(
    session: Annotated[Session, Depends(db)],
    type: str | None = None,
    state: str | None = None,
    iteration: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    items, total = az_repo.list_work_items(
        session, type=type, state=state, iteration=iteration,
        page=page, page_size=page_size,
    )
    return {
        "items": [WorkItemOut.model_validate(i).model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/pull-requests")
def list_pull_requests(session: Annotated[Session, Depends(db)]) -> dict:
    prs = az_repo.list_pull_requests(session, limit=100)
    return {"items": [PullRequestOut.model_validate(p).model_dump() for p in prs]}
