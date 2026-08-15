"""Analysis, job and agent models."""
from __future__ import annotations

from datetime import datetime

from app.core.json import SafeJSON
from app.core.types import utcnow
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TestMatrixAnalysis(Base):
    __tablename__ = "test_matrix_analyses"
    __table_args__ = (
        Index("ix_analysis_work_item_generated", "work_item_id", "generated_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_items.id"), nullable=False
    )
    coverage_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    missing_ac_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    existing_tests_reused: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_tests_required: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    potentially_redundant_tests: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="REVIEW_REQUIRED")
    is_new_functionality: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    details: Mapped[dict[str, Any]] = mapped_column(SafeJSON, nullable=False, default=dict)
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    work_item: Mapped["WorkItem"] = relationship(back_populates="analyses")  # noqa: F821


class TestGenerationCandidate(Base):
    __tablename__ = "test_generation_candidates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_items.id"), nullable=False
    )
    analysis_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("test_matrix_analyses.id")
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    acceptance_criterion_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    framework: Mapped[str] = mapped_column(String(16), nullable=False, default="both")
    scenario: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected: Mapped[str] = mapped_column(Text, nullable=False, default="")
    generated_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="proposed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class AgentJob(Base):
    __tablename__ = "agent_jobs"
    __table_args__ = (Index("ix_agent_jobs_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    trigger: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    params: Mapped[dict[str, Any]] = mapped_column(SafeJSON, nullable=False, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(SafeJSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    schedule: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEVER")
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ReportArchive(Base):
    __tablename__ = "report_archives"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    sprint_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    html_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    pdf_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    snapshot: Mapped[dict[str, Any]] = mapped_column(SafeJSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="GENERATED")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="log")
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
