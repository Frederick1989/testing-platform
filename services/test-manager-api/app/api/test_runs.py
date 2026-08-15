"""Test runs and results router (ingestion, trigger, query)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db
from app.core.auth import require_token
from app.core.errors import BadRequestError, NotFoundError
from app.core.types import JobType
from app.repositories import tests as test_repo
from app.schemas.tests import CanonicalTestRun, ExecuteRequest

router = APIRouter(tags=["test-runs"])


@router.post("/test-runs/ingest", status_code=202)
async def ingest_results(
    run: CanonicalTestRun,
    session: Annotated[Session, Depends(db)],
) -> dict:
    from app.services.ingestion import ingest_canonical_run

    try:
        return await ingest_canonical_run(session, run)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise BadRequestError(f"ingestion failed: {exc}") from exc


@router.post("/test-runs/execute", status_code=202)
async def execute_run(
    body: ExecuteRequest,
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    from app.jobs.scheduler import enqueue_job

    job_id = enqueue_job(
        JobType.TEST_EXECUTION,
        {
            "framework": body.framework,
            "environment": body.environment,
            "branch": body.branch,
            "commit_sha": body.commit_sha,
        },
        trigger="manual",
    )
    return {"job_id": job_id, "status": "QUEUED"}


@router.get("/test-runs")
def list_runs(
    session: Annotated[Session, Depends(db)],
    framework: str | None = None,
    environment: str | None = None,
    limit: int = 50,
) -> dict:
    runs = test_repo.list_test_runs(session, framework=framework, environment=environment, limit=limit)
    return {
        "items": [
            {
                "run_id": r.run_id, "framework": r.framework,
                "environment": r.environment, "branch": r.branch,
                "commit_sha": r.commit_sha, "status": r.status,
                "total": r.total, "passed": r.passed, "failed": r.failed,
                "skipped": r.skipped, "flaky": r.flaky,
                "error_count": r.error_count, "started_at": r.started_at,
                "completed_at": r.completed_at, "duration_ms": r.duration_ms,
                "report_location": r.report_location, "created_at": r.created_at,
            }
            for r in runs
        ]
    }


@router.get("/test-runs/{run_id}")
def get_run(
    run_id: str,
    session: Annotated[Session, Depends(db)],
) -> dict:
    run = test_repo.get_test_run(session, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")
    return {
        "run_id": run.run_id, "framework": run.framework,
        "environment": run.environment, "branch": run.branch,
        "commit_sha": run.commit_sha, "status": run.status,
        "total": run.total, "passed": run.passed, "failed": run.failed,
        "skipped": run.skipped, "flaky": run.flaky, "error_count": run.error_count,
        "started_at": run.started_at, "completed_at": run.completed_at,
        "duration_ms": run.duration_ms, "report_location": run.report_location,
    }


@router.get("/test-runs/{run_id}/results")
def run_results(
    run_id: str,
    session: Annotated[Session, Depends(db)],
) -> dict:
    run = test_repo.get_test_run(session, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")
    results = test_repo.list_results_for_run(session, run.id)
    return {"items": [_result_out(r) for r in results], "total": len(results)}


@router.get("/test-results")
def list_results(
    session: Annotated[Session, Depends(db)],
    run_id: int | None = None,
    status: str | None = None,
    test_case_key: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    items, total = test_repo.list_results(
        session, run_id=run_id, status=status,
        test_case_key=test_case_key, page=page, page_size=page_size,
    )
    return {"items": [_result_out(r) for r in items], "total": total,
            "page": page, "page_size": page_size}


@router.get("/test-results/{result_id}")
def get_result(
    result_id: int,
    session: Annotated[Session, Depends(db)],
) -> dict:
    r = test_repo.get_result(session, result_id)
    if r is None:
        raise NotFoundError(f"result {result_id} not found")
    return _result_out(r)


def _result_out(r) -> dict:
    return {
        "id": r.id, "test_run_id": r.test_run_id,
        "test_case_id": r.test_case_id, "scenario_id": r.scenario_id,
        "implementation_id": r.implementation_id, "framework": r.framework,
        "suite": r.suite, "title": r.title, "status": r.status,
        "duration_ms": r.duration_ms, "environment": r.environment,
        "branch": r.branch, "commit_sha": r.commit_sha,
        "started_at": r.started_at, "completed_at": r.completed_at,
        "error": r.error, "stack_trace": r.stack_trace,
        "artifacts": r.artifacts, "retries": r.retries, "is_flaky": r.is_flaky,
    }
