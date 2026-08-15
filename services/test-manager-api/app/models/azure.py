"""Azure DevOps integration models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.json import SafeJSON

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Iteration(Base):
    __tablename__ = "iterations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    azure_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finish_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    work_items: Mapped[list["WorkItem"]] = relationship(back_populates="iteration")


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        Index("ix_work_items_type", "type"),
        Index("ix_work_items_state", "state"),
        Index("ix_work_items_iteration_id", "iteration_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    azure_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    acceptance_criteria_raw: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    assigned_to: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    iteration_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("iterations.id")
    )
    iteration_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    area_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(SafeJSON, nullable=False, default=list)
    url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    parent_azure_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    iteration: Mapped["Iteration"] = relationship(back_populates="work_items")
    acceptance_criteria: Mapped[list["AcceptanceCriterion"]] = relationship(  # noqa: F821
        back_populates="work_item", cascade="all, delete-orphan"
    )
    comments: Mapped[list["AzureComment"]] = relationship(
        back_populates="work_item", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["TestMatrixAnalysis"]] = relationship(  # noqa: F821
        back_populates="work_item", cascade="all, delete-orphan"
    )


class AzureComment(Base):
    __tablename__ = "azure_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_items.id"), nullable=False
    )
    azure_comment_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    work_item: Mapped[WorkItem] = relationship(back_populates="comments")


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    azure_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    repo: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    target_ref: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    author: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    commit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AzureSyncLog(Base):
    __tablename__ = "azure_sync_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING")
    error: Mapped[str | None] = mapped_column(Text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "upserted": self.upserted,
            "status": self.status,
            "error": self.error,
        }
