"""Notification orchestration with deduplication and cooldowns."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.adapters.notifications import NotificationProvider, build_provider
from app.config import settings
from app.core.events import DomainEvent, bus
from app.db import SessionLocal
from app.repositories import jobs as job_repo

logger = logging.getLogger("app.notifications.service")

_DEFAULT_COOLDOWN: dict[str, int] = {
    "test_failure": 900,
    "flaky_detected": 3600,
    "defect_opened": 3600,
    "defect_critical": 1800,
    "story_blocked": 1800,
    "story_uat_ready": 3600,
    "coverage_gap": 86400,
    "pr_created": 0,
    "nightly_regression": 0,
    "run_completed": 0,
}


class NotificationService:
    def __init__(self, provider: NotificationProvider | None = None):
        self._provider = provider or build_provider()

    async def send(self, *, event_type: str, subject: str, body: str,
                   dedup_key: str = "", metadata: dict[str, Any] | None = None) -> None:
        if not settings.notifications_enabled:
            return
        cooldown = _DEFAULT_COOLDOWN.get(event_type, 0)
        with SessionLocal() as session:
            if dedup_key and job_repo.notification_recently_sent(
                session, dedup_key, cooldown
            ):
                job_repo.create_notification(
                    session,
                    type=event_type,
                    provider=self._provider.name,
                    subject=subject,
                    body=body,
                    dedup_key=dedup_key,
                    cooldown_seconds=cooldown,
                ).status = "SUPPRESSED"
                session.commit()
                return

            notification = job_repo.create_notification(
                session,
                type=event_type,
                provider=self._provider.name,
                subject=subject,
                body=body,
                dedup_key=dedup_key,
                cooldown_seconds=cooldown,
            )
            ok = await self._provider.send(subject=subject, body=body, metadata=metadata)
            notification.status = "SENT" if ok else "FAILED"
            notification.sent_at = datetime.now(timezone.utc)
            if not ok:
                notification.error = "provider send failed"
            session.commit()


_notification_service = NotificationService()


async def on_domain_event(event: DomainEvent) -> None:
    """Route domain events to notifications with meaningful, deduplicated messages."""
    p = event.payload
    subject = body = ""
    dedup = ""
    meta = None
    if event.type == "test_failure":
        subject = f"Test failure: {p.get('failed_count')} failed in run {p.get('run_id')}"
        body = f"Framework {p.get('framework')} — see test runs for details."
        dedup = f"failure:{p.get('run_id')}"
    elif event.type == "flaky_detected":
        subject = f"Flaky tests detected ({p.get('flaky_count')})"
        body = f"Run {p.get('run_id')} contained flaky results."
        dedup = f"flaky:{p.get('run_id')}"
    elif event.type == "coverage_gap":
        subject = f"Coverage gap: story {p.get('azure_id')} missing {p.get('missing')} AC"
        body = f"{p.get('title')} has acceptance criteria without test coverage."
        dedup = f"coverage:{p.get('work_item_id')}"
    elif event.type == "pr_created":
        subject = f"Test PR created for story {p.get('story_azure_id')}"
        body = f"Branch {p.get('branch')}: {p.get('pr_url', 'local branch only')}"
        dedup = f"pr:{p.get('branch')}"
    elif event.type == "nightly_regression":
        subject = "Nightly regression failure"
        body = f"New failures: {p.get('new_failures', 0)}. Repeated: {p.get('repeated', 0)}."
        dedup = f"nightly:{p.get('run_id')}"
    elif event.type == "run_completed":
        subject = f"Run completed: {p.get('run_id')}"
        body = (f"{p.get('passed')} passed, {p.get('failed')} failed, "
                f"{p.get('flaky')} flaky of {p.get('total')}.")
    if subject:
        await _notification_service.send(
            event_type=event.type, subject=subject, body=body,
            dedup_key=dedup, metadata=meta,
        )


def register_handlers() -> None:
    bus.subscribe_many({event_type: [on_domain_event] for event_type in [
        "test_failure", "flaky_detected", "coverage_gap", "pr_created",
        "nightly_regression", "run_completed",
    ]})
