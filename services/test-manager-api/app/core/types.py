"""Canonical enums used across the platform."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

__version__ = "0.1.0"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TestStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    FLAKY = "FLAKY"
    ERROR = "ERROR"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobType(StrEnum):
    AZURE_SYNC = "azure_sync"
    AZURE_SYNC_WORK_ITEMS = "azure_sync_work_items"
    AZURE_SYNC_PR = "azure_sync_pull_requests"
    AZURE_SYNC_ITERATIONS = "azure_sync_iterations"
    TEST_MATRIX_ANALYSIS = "test_matrix_analysis"
    TEST_GENERATION = "test_generation"
    TEST_EXECUTION = "test_execution"
    REPORT_GENERATION = "report_generation"
    NIGHTLY_REGRESSION = "nightly_regression"
    DEMO_RUN = "demo_run"
    DEMO_SEED = "demo_seed"


class Framework(StrEnum):
    API = "api"
    UI = "ui"
    PLAYWRIGHT = "playwright"
    PYTEST = "pytest"
    MANUAL = "manual"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DefectState(StrEnum):
    NEW = "New"
    ACTIVE = "Active"
    RESOLVED = "Resolved"
    CLOSED = "Closed"
    REMOVED = "Removed"


class WorkItemType(StrEnum):
    EPIC = "Epic"
    FEATURE = "Feature"
    USER_STORY = "User Story"
    TASK = "Task"
    BUG = "Bug"
    ISSUE = "Issue"


class CoverageStatus(StrEnum):
    COVERED = "COVERED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    NOT_COVERED = "NOT_COVERED"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class AnalysisStatus(StrEnum):
    COVERED = "COVERED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    NOT_COVERED = "NOT_COVERED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CandidateStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    GENERATED = "generated"


class NotificationType(StrEnum):
    TEST_FAILURE = "test_failure"
    FLAKY_DETECTED = "flaky_detected"
    DEFECT_OPENED = "defect_opened"
    DEFECT_CRITICAL = "defect_critical"
    STORY_BLOCKED = "story_blocked"
    STORY_UAT_READY = "story_uat_ready"
    COVERAGE_GAP = "coverage_gap"
    PR_CREATED = "pr_created"
    NIGHTLY_REGRESSION = "nightly_regression"
    RUN_COMPLETED = "run_completed"


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    SUPPRESSED = "SUPPRESSED"
