"""Agent metadata: human-readable agent -> job type mapping for the UI/API."""
from __future__ import annotations

from app.core.types import JobType

AGENT_JOBS: dict[str, JobType] = {
    "azure-sync": JobType.AZURE_SYNC,
    "test-execution": JobType.TEST_EXECUTION,
    "test-matrix": JobType.TEST_MATRIX_ANALYSIS,
    "test-generation": JobType.TEST_GENERATION,
    "nightly-regression": JobType.NIGHTLY_REGRESSION,
    "report-generation": JobType.REPORT_GENERATION,
}

AGENT_DEFAULTS: list[dict] = [
    {"name": "azure-sync", "schedule": "every 5 minutes (cron configurable)", "job": "azure_sync"},
    {"name": "test-execution", "schedule": "every 30 minutes (cron configurable)", "job": "test_execution"},
    {"name": "test-matrix", "schedule": "on demand", "job": "test_matrix_analysis"},
    {"name": "test-generation", "schedule": "on demand", "job": "test_generation"},
    {"name": "nightly-regression", "schedule": "02:00 UTC daily", "job": "nightly_regression"},
    {"name": "report-generation", "schedule": "Friday 15:00 UTC", "job": "report_generation"},
]
