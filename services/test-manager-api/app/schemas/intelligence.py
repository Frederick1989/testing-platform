"""Intelligence, jobs, reports, notification schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.types import AnalysisStatus, JobType


class SyncTestMatrixRequest(BaseModel):
    work_item_id: int
    force: bool = False


class CreateTestCasesRequest(BaseModel):
    work_item_id: int


class AnalysisResult(BaseModel):
    story_id: int
    coverage: float
    missing_acceptance_criteria: int
    existing_tests_reused: int
    new_tests_required: int
    potentially_redundant_tests: int
    status: AnalysisStatus


class JobResponse(BaseModel):
    job_id: str
    status: str
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class JobDetail(JobResponse):
    trigger: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int
    result: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    retry_count: int = 0
    max_retries: int = 0
    created_at: datetime


class JobCreate(BaseModel):
    type: JobType
    params: dict[str, Any] = Field(default_factory=dict)


class ReportGenerateRequest(BaseModel):
    sprint: str = ""
    include_matrix: bool = True


class ReportArchiveOut(BaseModel):
    id: int
    title: str
    sprint_name: str
    period_start: datetime | None
    period_end: datetime | None
    generated_at: datetime
    status: str
    created_by: str


class DemoRunRequest(BaseModel):
    iterations: int = 10
    failure_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    flaky_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    framework: str = "both"
    environment: str = "qa"
