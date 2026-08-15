"""Asynchronous job manager: DB-backed queue processed by an in-process worker."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from app.config import settings
from app.db import SessionLocal
from app.repositories import jobs as job_repo

logger = logging.getLogger("app.jobs")

JobHandler = Callable[..., Awaitable[dict[str, Any]]]


class JobManager:
    def __init__(self, registry: dict[str, JobHandler], concurrency: int | None = None):
        self._registry = registry
        self._concurrency = concurrency or settings.job_worker_concurrency
        self._tasks: set[asyncio.Task] = set()
        self._stopped = asyncio.Event()

    async def run_worker(self) -> None:
        logger.info("job worker started (concurrency=%s)", self._concurrency)
        while not self._stopped.is_set():
            try:
                await self._poll()
            except Exception:  # noqa: BLE001
                logger.exception("job worker poll failed")
            await asyncio.sleep(1.0)

    async def _poll(self) -> None:
        to_process: list[str] = []
        with SessionLocal() as session:
            jobs = job_repo.next_queued_jobs(session, limit=self._concurrency)
            for job in jobs:
                if job.type not in self._registry:
                    job.status = "FAILED"
                    job.error = f"no handler for job type {job.type}"
                    job.completed_at = datetime.now(timezone.utc)
                    continue
                job.status = "RUNNING"
                job.started_at = datetime.now(timezone.utc)
                to_process.append(job.job_id)
            session.commit()
        for job_id in to_process:
            task = asyncio.create_task(self._process(job_id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _process(self, job_id: str) -> None:
        with SessionLocal() as session:
            job = job_repo.get_job(session, job_id)
            if job is None:
                return
            started = datetime.now(timezone.utc)
            error = ""
            result: dict[str, Any] = {}
            for attempt in range(job.max_retries + 1):
                try:
                    handler = self._registry[job.type]
                    result = await handler(session, job.params)
                    break
                except Exception as exc:  # noqa: BLE001
                    error = f"{type(exc).__name__}: {exc}"[:4000]
                    logger.warning("job %s attempt %s failed: %s",
                                   job_id, attempt + 1, error)
                    session.rollback()
                    if attempt < job.max_retries:
                        job.retry_count = attempt + 1
                        session.commit()
                        await asyncio.sleep(2 ** attempt)
                    else:
                        job.status = "FAILED"
            else:
                job.status = "FAILED"
                job.error = error
            if job.status != "FAILED":
                job.status = "COMPLETED"
                job.result = result
                job.error = error
                await self._publish_events(job.type, result)
            job.completed_at = datetime.now(timezone.utc)
            job.duration_ms = int((job.completed_at - started).total_seconds() * 1000)
            session.commit()
        logger.info("job %s completed", job_id)

    async def _publish_events(self, job_type: str, result: dict[str, Any]) -> None:
        from app.core.events import DomainEvent, bus
        from app.core.types import JobType

        events: list[DomainEvent] = []
        if job_type in (JobType.TEST_EXECUTION.value, JobType.DEMO_RUN.value):
            run_id = str(result.get("run_id") or "demo")
            events.append(
                DomainEvent(
                    "run_completed",
                    {"run_id": run_id, "passed": result.get("passed", 0),
                     "failed": result.get("failed", 0), "flaky": result.get("flaky", 0),
                     "total": result.get("total") or result.get("runs", 0)},
                )
            )
        elif job_type == JobType.TEST_MATRIX_ANALYSIS.value:
            missing = int(result.get("missing_acceptance_criteria") or 0)
            if missing > 0:
                events.append(
                    DomainEvent(
                        "coverage_gap",
                        {"work_item_id": result.get("story_id"),
                         "azure_id": result.get("story_id"),
                         "missing": missing,
                         "title": result.get("story_title", "")},
                    )
                )
        if events:
            await bus.publish_all(events)

    async def shutdown(self) -> None:
        self._stopped.set()
        for task in list(self._tasks):
            task.cancel()
