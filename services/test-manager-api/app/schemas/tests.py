"""Test execution and matrix schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.types import TestStatus


class CanonicalTestResult(BaseModel):
    test_case_id: str = ""
    scenario_id: str = ""
    suite: str = ""
    title: str
    status: TestStatus
    duration_ms: int = 0
    error: str = ""
    stack_trace: str = ""
    artifacts: list[str] = Field(default_factory=list)
    retries: int = 0

    @field_validator("artifacts")
    @classmethod
    def _clean_artifacts(cls, v: list[str]) -> list[str]:
        return [a[:512] for a in v][:50]


class CanonicalTestRun(BaseModel):
    test_run_id: str
    framework: str
    suite: str = ""
    environment: str = "qa"
    branch: str = ""
    commit_sha: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    report_location: str = ""
    results: list[CanonicalTestResult] = Field(default_factory=list, max_length=10000)


class TestRunOut(BaseModel):
    run_id: str
    framework: str
    environment: str
    branch: str
    commit_sha: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int
    total: int
    passed: int
    failed: int
    skipped: int
    flaky: int
    error_count: int
    report_location: str
    status: str
    created_at: datetime


class TestResultOut(BaseModel):
    id: int
    test_run_id: int
    test_case_id: int | None
    scenario_id: int | None
    implementation_id: int | None
    framework: str
    suite: str
    title: str
    status: str
    duration_ms: int
    environment: str
    branch: str
    commit_sha: str
    started_at: datetime | None
    completed_at: datetime | None
    error: str
    stack_trace: str
    artifacts: list[str]
    retries: int
    is_flaky: bool


class TestCaseCreate(BaseModel):
    key: str | None = None
    title: str
    description: str = ""
    priority: str = "MEDIUM"
    suggested_framework: str = "both"


class TestCaseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    suggested_framework: str | None = None
    status: str | None = None


class TestCaseOut(BaseModel):
    id: int
    key: str
    title: str
    description: str
    priority: str
    suggested_framework: str
    status: str
    source: str
    created_at: datetime
    updated_at: datetime
    linked_story_ids: list[int] = []
    linked_ac_ids: list[int] = []


class ScenarioCreate(BaseModel):
    name: str
    description: str = ""
    steps: list[dict] = Field(default_factory=list)


class LinkRequest(BaseModel):
    work_item_id: int
    test_case_key: str
    acceptance_criterion_index: int | None = None
    rationale: str = ""


class ExecuteRequest(BaseModel):
    framework: str = Field(pattern="^(api|ui|playwright|pytest)$")
    environment: str = "qa"
    branch: str = "develop"
    commit_sha: str = ""
    selector: str = ""


class MatrixNode(BaseModel):
    key: str | None = None
    title: str
    status: str
    latest: TestResultOut | None = None
    previous: TestResultOut | None = None


class MatrixAcceptanceCriterion(BaseModel):
    id: int
    text: str
    status: str
    test_cases: list[MatrixNode]


class MatrixStory(BaseModel):
    work_item_id: int
    azure_id: int
    title: str
    url: str
    state: str
    iteration_name: str
    coverage: float
    uat_ready: bool
    defects: list[str]
    acceptance_criteria: list[MatrixAcceptanceCriterion]
