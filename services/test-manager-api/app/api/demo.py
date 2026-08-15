"""Demo endpoints — gated to demo/development environments."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db
from app.core.auth import require_token
from app.core.errors import DemoOnlyError
from app.core.types import JobType
from app.schemas.intelligence import DemoRunRequest

router = APIRouter(prefix="/demo", tags=["demo"])


def _guard() -> None:
    from app.config import settings

    if not settings.is_demo:
        raise DemoOnlyError("demo endpoints are only available in demo/development mode")


@router.post("/run", status_code=202)
async def demo_run(
    body: DemoRunRequest,
    session: Annotated[Session, Depends(db)],
    _: Annotated[str, Depends(require_token)],
) -> dict:
    _guard()
    from app.jobs.scheduler import enqueue_job

    job_id = enqueue_job(
        JobType.DEMO_RUN,
        {
            "iterations": body.iterations,
            "failure_rate": body.failure_rate,
            "flaky_rate": body.flaky_rate,
            "framework": body.framework,
            "environment": body.environment,
        },
        trigger="manual",
    )
    return {"job_id": job_id, "status": "QUEUED"}


@router.post("/seed", status_code=202)
async def demo_seed(
    session: Annotated[Session, Depends(db)],
    _: Annotated[str, Depends(require_token)],
) -> dict:
    _guard()
    from app.jobs.scheduler import enqueue_job

    job_id = enqueue_job(JobType.DEMO_SEED, {}, trigger="manual")
    return {"job_id": job_id, "status": "QUEUED"}


@router.post("/reset", status_code=202)
async def demo_reset(
    session: Annotated[Session, Depends(db)],
    _: Annotated[str, Depends(require_token)],
) -> dict:
    _guard()
    from sqlalchemy import delete, text

    from app.models.analysis import (
        Agent,
        AgentJob,
        Notification,
        ReportArchive,
        TestGenerationCandidate,
        TestMatrixAnalysis,
    )
    from app.models.azure import AzureComment, AzureSyncLog, Iteration, PullRequest, WorkItem
    from app.models.test import (
        AcceptanceCriterion,
        Defect,
        TestCase,
        TestDefectLink,
        TestImplementation,
        TestResult,
        TestRun,
        TestScenario,
        TestStoryLink,
    )

    for model in (
        TestResult, TestRun, TestDefectLink, Defect, TestStoryLink,
        TestImplementation, TestScenario, TestCase, AcceptanceCriterion,
        AzureComment, WorkItem, PullRequest, Iteration,
        TestMatrixAnalysis, TestGenerationCandidate, AgentJob, Agent,
        Notification, ReportArchive, AzureSyncLog,
    ):
        session.execute(delete(model))
    session.execute(text("ALTER SEQUENCE IF EXISTS test_results_id_seq RESTART WITH 1"))
    session.execute(text("ALTER SEQUENCE IF EXISTS test_runs_id_seq RESTART WITH 1"))
    session.execute(text("ALTER SEQUENCE IF EXISTS test_cases_id_seq RESTART WITH 1"))
    session.commit()
    return {"status": "RESET"}
