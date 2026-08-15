"""Test management, execution and defect models."""
from __future__ import annotations

from datetime import datetime

from app.core.json import SafeJSON
from app.core.types import utcnow
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (Index("ix_test_cases_status", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="auto")
    suggested_framework: Mapped[str] = mapped_column(
        String(16), nullable=False, default="both"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    scenarios: Mapped[list["TestScenario"]] = relationship(
        back_populates="test_case", cascade="all, delete-orphan"
    )
    implementations: Mapped[list["TestImplementation"]] = relationship(
        back_populates="test_case", cascade="all, delete-orphan"
    )
    story_links: Mapped[list["TestStoryLink"]] = relationship(
        back_populates="test_case", cascade="all, delete-orphan"
    )


class TestScenario(Base):
    __tablename__ = "test_scenarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    test_case_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("test_cases.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    steps: Mapped[list[Any]] = mapped_column(SafeJSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    test_case: Mapped[TestCase] = relationship(back_populates="scenarios")


class TestImplementation(Base):
    __tablename__ = "test_implementations"
    __table_args__ = (
        UniqueConstraint("test_case_id", "framework", "path", name="uq_impl_framework_path"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    test_case_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("test_cases.id"), nullable=False
    )
    framework: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    test_case: Mapped[TestCase] = relationship(back_populates="implementations")


class AcceptanceCriterion(Base):
    __tablename__ = "acceptance_criteria"
    __table_args__ = (
        UniqueConstraint("work_item_id", "sort_order", name="uq_ac_workitem_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_items.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_COVERED")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    work_item: Mapped["WorkItem"] = relationship(  # noqa: F821
        back_populates="acceptance_criteria"
    )
    story_links: Mapped[list["TestStoryLink"]] = relationship(
        back_populates="acceptance_criterion"
    )


class TestStoryLink(Base):
    __tablename__ = "test_story_links"
    __table_args__ = (
        UniqueConstraint(
            "work_item_id", "acceptance_criterion_id", "test_case_id",
            name="uq_storylink",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_items.id"), nullable=False
    )
    acceptance_criterion_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("acceptance_criteria.id"), nullable=True
    )
    test_case_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("test_cases.id"), nullable=False
    )
    coverage_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NOT_COVERED"
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    test_case: Mapped[TestCase] = relationship(back_populates="story_links")
    acceptance_criterion: Mapped[AcceptanceCriterion | None] = relationship(
        back_populates="story_links"
    )


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = (Index("ix_test_runs_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    framework: Mapped[str] = mapped_column(String(32), nullable=False)
    environment: Mapped[str] = mapped_column(String(64), nullable=False, default="qa")
    branch: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    flaky: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_location: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    results: Mapped[list["TestResult"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )


class TestResult(Base):
    __tablename__ = "test_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PASSED','FAILED','SKIPPED','BLOCKED','FLAKY','ERROR')",
            name="ck_test_result_status",
        ),
        Index("ix_test_results_test_case_id", "test_case_id"),
        Index("ix_test_results_status", "status"),
        Index("ix_test_results_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("test_runs.id"), nullable=False
    )
    implementation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("test_implementations.id")
    )
    test_case_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("test_cases.id")
    )
    scenario_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("test_scenarios.id")
    )
    framework: Mapped[str] = mapped_column(String(32), nullable=False)
    suite: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    environment: Mapped[str] = mapped_column(String(64), nullable=False, default="qa")
    branch: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stack_trace: Mapped[str] = mapped_column(Text, nullable=False, default="")
    artifacts: Mapped[list[Any]] = mapped_column(SafeJSON, nullable=False, default=list)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_flaky: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    test_run: Mapped[TestRun] = relationship(back_populates="results")


class Defect(Base):
    __tablename__ = "defects"
    __table_args__ = (
        Index("ix_defects_state", "state"),
        Index("ix_defects_severity", "severity"),
        Index("ix_defects_story_work_item_id", "story_work_item_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    azure_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="New")
    assigned_to: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    iteration_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    iteration_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    story_work_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_escaped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[list[str]] = mapped_column(SafeJSON, nullable=False, default=list)
    url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class TestDefectLink(Base):
    __tablename__ = "test_defect_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    defect_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("defects.id"), nullable=False
    )
    test_result_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("test_results.id")
    )
    test_case_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("test_cases.id")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    linked_by: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
