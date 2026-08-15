"""Flakiness detection from test result history."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.test import TestCase, TestResult


def flaky_tests(session: Session, *, min_runs: int = 3, window_days: int = 60) -> dict[str, Any]:

    stmt = select(TestResult).order_by(TestResult.test_case_id, TestResult.started_at)
    results = list(session.scalars(stmt))

    by_test: dict[int, list[TestResult]] = defaultdict(list)
    for r in results:
        if r.test_case_id:
            by_test[r.test_case_id].append(r)

    flaky: list[dict[str, Any]] = []
    for tc_id, rs in by_test.items():
        if len(rs) < min_runs:
            continue
        statuses = [r.status for r in rs]
        has_pass = "PASSED" in statuses
        has_fail = any(s in ("FAILED", "ERROR", "BLOCKED") for s in statuses)
        if has_pass and has_fail:
            tc = session.get(TestCase, tc_id)
            flaky.append(
                {
                    "test_case_id": tc_id,
                    "key": tc.key if tc else None,
                    "title": tc.title if tc else f"TestCase {tc_id}",
                    "runs": len(rs),
                    "passes": statuses.count("PASSED"),
                    "failures": sum(1 for s in statuses if s != "PASSED"),
                    "last_status": rs[-1].status,
                    "last_run_at": rs[-1].started_at,
                }
            )
    flaky.sort(key=lambda f: f["failures"], reverse=True)
    return {
        "count": len(flaky),
        "min_runs": min_runs,
        "tests": flaky,
    }


def regression_report(session: Session) -> dict[str, Any]:
    """New failures, recovered tests, repeatedly failing tests."""
    stmt = select(TestResult).order_by(TestResult.test_case_id, TestResult.started_at)
    results = list(session.scalars(stmt))
    by_test: dict[int, list[TestResult]] = defaultdict(list)
    for r in results:
        if r.test_case_id:
            by_test[r.test_case_id].append(r)

    new_failures: list[dict[str, Any]] = []
    recovered: list[dict[str, Any]] = []
    repeated: list[dict[str, Any]] = []
    for tc_id, rs in by_test.items():
        if len(rs) < 2:
            continue
        last, prev = rs[-1], rs[-2]
        tc = session.get(TestCase, tc_id)
        info = {
            "test_case_id": tc_id,
            "key": tc.key if tc else None,
            "title": tc.title if tc else f"TestCase {tc_id}",
            "last_status": last.status,
            "previous_status": prev.status,
        }
        if last.status in ("FAILED", "ERROR") and prev.status == "PASSED":
            new_failures.append(info)
        elif last.status == "PASSED" and prev.status in ("FAILED", "ERROR"):
            recovered.append(info)
        failures = sum(1 for r in rs if r.status in ("FAILED", "ERROR"))
        if failures >= 3:
            repeated.append(
                {
                    **info,
                    "failure_count": failures,
                    "runs": len(rs),
                    "failure_rate": round(failures / len(rs) * 100, 1),
                }
            )
    return {
        "new_failures": new_failures,
        "recovered": recovered,
        "repeated_failures": repeated,
        "counts": {
            "new_failures": len(new_failures),
            "recovered": len(recovered),
            "repeated_failures": len(repeated),
        },
    }


def test_health_stats(session: Session) -> dict[str, Any]:
    stmt = select(TestResult)
    results = list(session.scalars(stmt))
    total = len(results)
    if not total:
        return {"total": 0, "pass_rate": 0.0, "failure_rate": 0.0, "flakiness_rate": 0.0,
                "avg_duration_ms": 0, "p95_duration_ms": 0}
    passed = sum(1 for r in results if r.status == "PASSED")
    failed = sum(1 for r in results if r.status in ("FAILED", "ERROR", "BLOCKED"))
    flaky = sum(1 for r in results if r.status == "FLAKY" or r.is_flaky)
    durations = sorted(r.duration_ms for r in results)
    return {
        "total": total,
        "pass_rate": round(passed / total * 100, 1),
        "failure_rate": round(failed / total * 100, 1),
        "flakiness_rate": round(flaky / total * 100, 1),
        "avg_duration_ms": round(sum(durations) / len(durations), 1),
        "p95_duration_ms": durations[int(len(durations) * 0.95) - 1],
    }
