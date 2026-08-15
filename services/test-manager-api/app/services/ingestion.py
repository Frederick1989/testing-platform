"""Test result ingestion: canonical -> normalized -> persisted + events."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.parsers import PARSERS
from app.core.events import DomainEvent, bus
from app.core.types import NotificationType, TestStatus
from app.repositories import tests as test_repo
from app.schemas.tests import CanonicalTestRun

logger = logging.getLogger("app.ingestion")

_MAYBE_FLAKY = {TestStatus.FLAKY}


def _resolve_test_case_id(session: Session, result: Any) -> int | None:
    """Match a canonical result to an existing TestCase by key, or by title."""
    if result.test_case_id:
        tc = test_repo.get_test_case(session, result.test_case_id)
        if tc:
            return tc.id
    if result.title:
        from app.models.test import TestCase

        tc = session.execute(
            TestCase.__table__.select().where(TestCase.title == result.title).limit(1)
        ).first()
        if tc:
            return tc["id"]
    return None


async def ingest_canonical_run(session: Session, run: CanonicalTestRun) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    existing = test_repo.get_test_run(session, run.test_run_id)
    if existing is not None:
        return {"status": "ALREADY_INGESTED", "run_id": run.test_run_id}

    db_run = test_repo.create_test_run(
        session,
        run_id=run.test_run_id,
        framework=run.framework,
        environment=run.environment,
        branch=run.branch,
        commit_sha=run.commit_sha,
        started_at=run.started_at or now,
    )
    session.flush()

    passed = failed = skipped = flaky = error_count = 0
    results = []
    for r in run.results:
        status = r.status
        if status == TestStatus.PASSED:
            passed += 1
        elif status == TestStatus.FAILED:
            failed += 1
        elif status == TestStatus.SKIPPED:
            skipped += 1
        elif status == TestStatus.FLAKY:
            flaky += 1
        else:
            error_count += 1
        results.append(r)

    db_run.total = len(results)
    db_run.passed = passed
    db_run.failed = failed
    db_run.skipped = skipped
    db_run.flaky = flaky
    db_run.error_count = error_count
    db_run.completed_at = run.completed_at or now
    db_run.duration_ms = (
        run.completed_at and run.started_at
    ) and int((run.completed_at - run.started_at).total_seconds() * 1000) or 0
    db_run.report_location = run.report_location
    db_run.status = "COMPLETED"

    for r in results:
        from app.models.test import TestResult

        db_result = TestResult(
            test_run_id=db_run.id,
            test_case_id=_resolve_test_case_id(session, r),
            framework=run.framework,
            suite=r.suite,
            title=r.title,
            status=r.status.value,
            duration_ms=r.duration_ms,
            environment=run.environment,
            branch=run.branch,
            commit_sha=run.commit_sha,
            started_at=run.started_at or now,
            completed_at=run.completed_at or now,
            error=r.error[:4000],
            stack_trace=r.stack_trace[:8000],
            artifacts=r.artifacts,
            retries=r.retries,
            is_flaky=r.status in _MAYBE_FLAKY,
        )
        session.add(db_result)
    session.flush()

    session.commit()

    events: list[DomainEvent] = [
        DomainEvent(
            NotificationType.RUN_COMPLETED.value,
            {
                "run_id": run.test_run_id,
                "framework": run.framework,
                "total": db_run.total,
                "passed": db_run.passed,
                "failed": db_run.failed,
                "flaky": db_run.flaky,
            },
        )
    ]
    if failed:
        events.append(
            DomainEvent(
                NotificationType.TEST_FAILURE.value,
                {
                    "run_id": run.test_run_id,
                    "failed_count": failed,
                    "framework": run.framework,
                },
            )
        )
    if flaky:
        events.append(
            DomainEvent(
                NotificationType.FLAKY_DETECTED.value,
                {"run_id": run.test_run_id, "flaky_count": flaky},
            )
        )
    await bus.publish_all(events)

    return {
        "status": "INGESTED",
        "run_id": run.test_run_id,
        "total": db_run.total,
        "passed": db_run.passed,
        "failed": db_run.failed,
        "skipped": db_run.skipped,
        "flaky": db_run.flaky,
        "error_count": db_run.error_count,
    }


def parse_framework_output(framework: str, raw: dict[str, Any]) -> CanonicalTestRun:
    key = framework.lower()
    if key in ("api", "pytest", "junit"):
        parser = PARSERS["junit"]
        return parser(raw.get("xml", ""), framework=key)
    if key in ("playwright", "ui", "web"):
        parser = PARSERS["playwright"]
        return parser(raw, default_branch=raw.get("branch", ""),
                      default_commit=raw.get("commit_sha", ""))
    return PARSERS["canonical"](raw)
