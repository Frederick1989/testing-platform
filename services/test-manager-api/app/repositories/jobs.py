"""Data access for jobs, agents, notifications, reports."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import Agent, AgentJob, Notification, ReportArchive


def enqueue_job(session: Session, *, job_id: str, type: str, params: dict,
                trigger: str, max_retries: int = 2) -> AgentJob:
    job = AgentJob(
        job_id=job_id, type=type, status="QUEUED", trigger=trigger,
        params=params, max_retries=max_retries,
        created_at=datetime.now(timezone.utc),
    )
    session.add(job)
    return job


def get_job(session: Session, job_id: str) -> AgentJob | None:
    return session.scalar(select(AgentJob).where(AgentJob.job_id == job_id))


def get_job_by_pk(session: Session, pk: int) -> AgentJob | None:
    return session.get(AgentJob, pk)


def list_jobs(session: Session, *, status: str | None = None,
              limit: int = 100) -> Sequence[AgentJob]:
    stmt = select(AgentJob)
    if status:
        stmt = stmt.where(AgentJob.status == status)
    return session.scalars(stmt.order_by(AgentJob.created_at.desc()).limit(limit)).all()


def next_queued_jobs(session: Session, limit: int = 5) -> Sequence[AgentJob]:
    return session.scalars(
        select(AgentJob)
        .where(AgentJob.status == "QUEUED")
        .order_by(AgentJob.created_at)
        .limit(limit)
    ).all()


def upsert_agent(session: Session, *, name: str, schedule: str,
                 enabled: bool = True) -> Agent:
    agent = session.scalar(select(Agent).where(Agent.name == name))
    if agent is None:
        agent = Agent(name=name, schedule=schedule, enabled=enabled)
        session.add(agent)
    else:
        agent.schedule = schedule
        agent.enabled = enabled
    return agent


def list_agents(session: Session) -> Sequence[Agent]:
    return session.scalars(select(Agent).order_by(Agent.name)).all()


def get_agent(session: Session, name: str) -> Agent | None:
    return session.scalar(select(Agent).where(Agent.name == name))


def record_agent_run(session: Session, name: str, *, ok: bool, error: str = "") -> None:
    agent = get_agent(session, name)
    if agent is None:
        return
    agent.last_run_at = datetime.now(timezone.utc)
    agent.last_status = "OK" if ok else "FAILED"
    agent.run_count = (agent.run_count or 0) + 1
    agent.last_error = error


def create_notification(session: Session, *, type: str, provider: str, subject: str,
                        body: str, dedup_key: str = "", cooldown_seconds: int = 0) -> Notification:
    now = datetime.now(timezone.utc)
    n = Notification(
        type=type, provider=provider, subject=subject, body=body,
        status="PENDING", dedup_key=dedup_key, cooldown_seconds=cooldown_seconds,
        created_at=now,
    )
    session.add(n)
    return n


def notification_recently_sent(session: Session, dedup_key: str,
                               cooldown_seconds: int) -> bool:
    if not dedup_key:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)
    row = session.scalar(
        select(Notification.id)
        .where(
            Notification.dedup_key == dedup_key,
            Notification.status == "SENT",
            Notification.sent_at >= cutoff,
        )
        .limit(1)
    )
    return row is not None


def list_notifications(session: Session, limit: int = 100) -> Sequence[Notification]:
    return session.scalars(
        select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    ).all()


def create_report_archive(session: Session, *, title: str, sprint_name: str,
                          period_start: datetime | None, period_end: datetime | None,
                          html_path: str, pdf_path: str, snapshot: dict,
                          created_by: str = "system") -> ReportArchive:
    r = ReportArchive(
        title=title, sprint_name=sprint_name, period_start=period_start,
        period_end=period_end, generated_at=datetime.now(timezone.utc),
        html_path=html_path, pdf_path=pdf_path, snapshot=snapshot,
        status="GENERATED", created_by=created_by,
    )
    session.add(r)
    return r


def list_report_archives(session: Session, limit: int = 100) -> Sequence[ReportArchive]:
    return session.scalars(
        select(ReportArchive).order_by(ReportArchive.generated_at.desc()).limit(limit)
    ).all()


def get_report_archive(session: Session, archive_id: int) -> ReportArchive | None:
    return session.get(ReportArchive, archive_id)
