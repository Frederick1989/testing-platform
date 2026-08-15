"""Reports, notifications, agents, jobs, dashboard, intelligence, demo routers."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import db
from app.core.auth import require_token
from app.core.errors import NotFoundError
from app.core.types import JobType
from app.repositories import jobs as job_repo

reports_router = APIRouter(prefix="/reports", tags=["reports"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])
agents_router = APIRouter(prefix="/agents", tags=["agents"])
jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])
dashboard_router = APIRouter(
    prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_token)]
)
intelligence_router = APIRouter(
    tags=["intelligence"], dependencies=[Depends(require_token)]
)


@reports_router.post("/generate", status_code=202)
async def generate_report(
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
    sprint: str = "",
    include_matrix: bool = True,
) -> dict:
    from app.jobs.scheduler import enqueue_job

    job_id = enqueue_job(
        JobType.REPORT_GENERATION,
        {"sprint": sprint, "include_matrix": include_matrix},
        trigger="manual",
    )
    return {"job_id": job_id, "status": "QUEUED"}


@reports_router.get("/latest")
def latest_report(session: Annotated[Session, Depends(db)]) -> dict:
    archives = job_repo.list_report_archives(session, limit=1)
    if not archives:
        raise NotFoundError("no reports generated yet")
    a = archives[0]
    return {
        "id": a.id, "title": a.title, "sprint_name": a.sprint_name,
        "generated_at": a.generated_at, "status": a.status,
        "html_path": a.html_path, "pdf_path": a.pdf_path,
        "snapshot": a.snapshot,
    }


@reports_router.get("/archive")
def report_archive(session: Annotated[Session, Depends(db)]) -> dict:
    rows = job_repo.list_report_archives(session)
    return {
        "items": [
            {
                "id": a.id, "title": a.title, "sprint_name": a.sprint_name,
                "period_start": a.period_start, "period_end": a.period_end,
                "generated_at": a.generated_at, "status": a.status,
                "created_by": a.created_by,
            }
            for a in rows
        ]
    }


@reports_router.get("/archive/{archive_id}")
def archive_detail(archive_id: int, session: Annotated[Session, Depends(db)]) -> dict:
    a = job_repo.get_report_archive(session, archive_id)
    if a is None:
        raise NotFoundError(f"archive {archive_id} not found")
    return {
        "id": a.id, "title": a.title, "sprint_name": a.sprint_name,
        "period_start": a.period_start, "period_end": a.period_end,
        "generated_at": a.generated_at, "status": a.status,
        "html_path": a.html_path, "pdf_path": a.pdf_path,
        "snapshot": a.snapshot, "created_by": a.created_by,
    }


def _serve_artifact(path: str) -> FileResponse:
    p = Path(path)
    if not p.is_file():
        raise NotFoundError(f"artifact not found: {path}")
    return FileResponse(p, media_type="application/octet-stream")


@reports_router.get("/archive/{archive_id}/html")
def archive_html(archive_id: int, session: Annotated[Session, Depends(db)]) -> FileResponse:
    a = job_repo.get_report_archive(session, archive_id)
    if a is None:
        raise NotFoundError(f"archive {archive_id} not found")
    return FileResponse(a.html_path, media_type="text/html")


@reports_router.get("/archive/{archive_id}/pdf")
def archive_pdf(archive_id: int, session: Annotated[Session, Depends(db)]) -> FileResponse:
    a = job_repo.get_report_archive(session, archive_id)
    if a is None:
        raise NotFoundError(f"archive {archive_id} not found")
    return FileResponse(a.pdf_path, media_type="application/pdf")


@notifications_router.get("")
def list_notifications(session: Annotated[Session, Depends(db)]) -> dict:
    rows = job_repo.list_notifications(session)
    return {
        "items": [
            {
                "id": n.id, "type": n.type, "provider": n.provider,
                "subject": n.subject, "status": n.status,
                "sent_at": n.sent_at, "created_at": n.created_at,
                "error": n.error,
            }
            for n in rows
        ]
    }


@notifications_router.post("/test")
async def test_notification(
    _: Annotated[str, Depends(require_token)],
) -> dict:
    from app.services.notifications import _notification_service

    await _notification_service.send(
        event_type="run_completed", subject="Test notification",
        body="The UAT platform notification system is working.",
    )
    return {"status": "SENT"}


@agents_router.get("")
def list_agents(session: Annotated[Session, Depends(db)]) -> dict:
    rows = job_repo.list_agents(session)
    return {
        "items": [
            {
                "name": a.name, "schedule": a.schedule, "enabled": a.enabled,
                "last_run_at": a.last_run_at, "last_status": a.last_status,
                "run_count": a.run_count, "last_error": a.last_error,
            }
            for a in rows
        ]
    }


@agents_router.post("/{name}/run", status_code=202)
async def run_agent(
    name: str,
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    from app.adapters.agents_meta import AGENT_JOBS

    job_type = AGENT_JOBS.get(name)
    if job_type is None:
        raise NotFoundError(f"unknown agent {name}")
    from app.jobs.scheduler import enqueue_job

    job_id = enqueue_job(job_type, {}, trigger="manual")
    return {"job_id": job_id, "status": "QUEUED", "agent": name}


@jobs_router.post("", status_code=202)
async def create_job(
    body: dict,
    _: Annotated[str, Depends(require_token)],
) -> dict:
    from app.jobs.scheduler import enqueue_job

    job_type = JobType(body.get("type", ""))
    job_id = enqueue_job(job_type, body.get("params", {}), trigger="manual")
    return {"job_id": job_id, "status": "QUEUED", "type": job_type.value}


@jobs_router.get("")
def list_jobs(
    session: Annotated[Session, Depends(db)],
    status: str | None = None,
) -> dict:
    rows = job_repo.list_jobs(session, status=status)
    return {
        "items": [
            {
                "job_id": j.job_id, "type": j.type, "status": j.status,
                "trigger": j.trigger, "params": j.params,
                "started_at": j.started_at, "completed_at": j.completed_at,
                "duration_ms": j.duration_ms, "error": j.error,
                "created_at": j.created_at, "retry_count": j.retry_count,
            }
            for j in rows
        ]
    }


@jobs_router.get("/{job_id}")
def get_job(job_id: str, session: Annotated[Session, Depends(db)]) -> dict:
    j = job_repo.get_job(session, job_id)
    if j is None:
        raise NotFoundError(f"job {job_id} not found")
    return {
        "job_id": j.job_id, "type": j.type, "status": j.status,
        "trigger": j.trigger, "params": j.params, "result": j.result,
        "started_at": j.started_at, "completed_at": j.completed_at,
        "duration_ms": j.duration_ms, "error": j.error,
        "retry_count": j.retry_count, "max_retries": j.max_retries,
        "created_at": j.created_at,
    }


@jobs_router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    j = job_repo.get_job(session, job_id)
    if j is None:
        raise NotFoundError(f"job {job_id} not found")
    if j.status == "QUEUED":
        j.status = "CANCELLED"
        session.commit()
        return {"job_id": job_id, "status": "CANCELLED"}
    raise HTTPException(status_code=409, detail="job is not cancellable in its current state")


@dashboard_router.get("/summary")
def dashboard_summary(session: Annotated[Session, Depends(db)]) -> dict:
    from app.services.dashboard import summary

    return summary(session)


@intelligence_router.get("/sprints")
def sprints(session: Annotated[Session, Depends(db)]) -> dict:
    from app.services.sprints import list_sprint_summaries

    return {"items": list_sprint_summaries(session)}


@intelligence_router.get("/sprints/{iteration_id}")
def sprint_detail(iteration_id: int, session: Annotated[Session, Depends(db)]) -> dict:
    from app.models.azure import Iteration
    from app.services.sprints import sprint_metrics

    iteration = session.get(Iteration, iteration_id)
    if iteration is None:
        raise NotFoundError(f"iteration {iteration_id} not found")
    return sprint_metrics(session, iteration)


@intelligence_router.get("/velocity")
def velocity(session: Annotated[Session, Depends(db)]) -> dict:
    from app.services.sprints import velocity_series

    return {"items": velocity_series(session)}


@intelligence_router.get("/flaky-tests")
def flaky_tests(session: Annotated[Session, Depends(db)], min_runs: int = 3) -> dict:
    from app.services.flakiness import flaky_tests

    return flaky_tests(session, min_runs=min_runs)


@intelligence_router.get("/regression")
def regression(session: Annotated[Session, Depends(db)]) -> dict:
    from app.services.flakiness import regression_report

    return regression_report(session)


@intelligence_router.get("/risks")
def risks(session: Annotated[Session, Depends(db)]) -> dict:
    from app.services.risks import compute_risks

    return {"items": compute_risks(session)}
