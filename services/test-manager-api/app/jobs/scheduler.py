"""Deterministic scheduler for agents using APScheduler."""
from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.core.types import JobType
from app.db import SessionLocal
from app.repositories import jobs as job_repo

logger = logging.getLogger("app.scheduler")


def enqueue_job(job_type: JobType, params: dict[str, Any] | None = None,
                trigger: str = "schedule") -> str | None:
    from app.core.ids import job_id

    with SessionLocal() as session:
        job = job_repo.enqueue_job(
            session,
            job_id=job_id(),
            type=job_type.value,
            params=params or {},
            trigger=trigger,
        )
        session.commit()
        return job.job_id


def _job_id_factory() -> str:
    from app.core.ids import job_id

    return job_id()


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    if settings.agents_enabled and settings.schedule_azure_sync:
        scheduler.add_job(
            enqueue_job,
            CronTrigger.from_crontab(settings.schedule_azure_sync),
            args=[JobType.AZURE_SYNC, {}, "schedule"],
            id="azure-sync",
            replace_existing=True,
        )
    if settings.agents_enabled and settings.schedule_test_execution:
        scheduler.add_job(
            enqueue_job,
            CronTrigger.from_crontab(settings.schedule_test_execution),
            args=[JobType.TEST_EXECUTION, {"framework": "both"}, "schedule"],
            id="test-execution",
            replace_existing=True,
        )
    if settings.agents_enabled and settings.schedule_nightly_regression:
        scheduler.add_job(
            enqueue_job,
            CronTrigger.from_crontab(settings.schedule_nightly_regression),
            args=[JobType.NIGHTLY_REGRESSION, {}, "schedule"],
            id="nightly-regression",
            replace_existing=True,
        )
    if settings.agents_enabled and settings.schedule_report_generation:
        scheduler.add_job(
            enqueue_job,
            CronTrigger.from_crontab(settings.schedule_report_generation),
            args=[JobType.REPORT_GENERATION, {}, "schedule"],
            id="report-generation",
            replace_existing=True,
        )

    scheduler.start()
    logger.info(
        "scheduler started: azure=%s execution=%s nightly=%s report=%s",
        settings.schedule_azure_sync,
        settings.schedule_test_execution,
        settings.schedule_nightly_regression,
        settings.schedule_report_generation,
    )
    return scheduler
