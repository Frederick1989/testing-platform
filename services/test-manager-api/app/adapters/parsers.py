"""Test result parsers: raw framework output -> CanonicalTestRun.

Parsers never talk to the database; they are pure transformations.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from app.core.types import TestStatus
from app.schemas.tests import CanonicalTestResult, CanonicalTestRun

_PLAYWRIGHT_STATUS = {
    "passed": TestStatus.PASSED,
    "failed": TestStatus.FAILED,
    "skipped": TestStatus.SKIPPED,
    "timedOut": TestStatus.FAILED,
    "flaky": TestStatus.FLAKY,
    "interrupted": TestStatus.BLOCKED,
}

_JUNIT_STATUS = {
    "passed": TestStatus.PASSED,
    "failed": TestStatus.FAILED,
    "skipped": TestStatus.SKIPPED,
    "error": TestStatus.ERROR,
}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_playwright_json(data: dict[str, Any], *, default_env: str = "qa",
                         default_branch: str = "", default_commit: str = "") -> CanonicalTestRun:
    """Parse @playwright/test JSON reporter output (list of suites/run)."""
    started = _parse_dt(data.get("startedAt"))
    suite = data.get("suite") or {}
    results: list[CanonicalTestResult] = []
    for test in _walk_tests(suite):
        status = _PLAYWRIGHT_STATUS.get(test.get("status", ""), TestStatus.ERROR)
        errors = test.get("errors", [])
        error = errors[0].get("message", "")[:2000] if errors else ""
        stack = errors[0].get("stack", "")[:4000] if errors else ""
        results.append(
            CanonicalTestResult(
                title=test.get("title", ""),
                status=status,
                duration_ms=int(test.get("duration") or 0),
                error=error,
                stack_trace=stack,
                artifacts=[a.get("path", "") for a in test.get("attachments", [])],
                suite=".".join(str(t) for t in (test.get("fullTitle") or "").split(" › ")[:-1]),
            )
        )
    return CanonicalTestRun(
        test_run_id=data.get("test_run_id") or f"pw-{int((started or datetime.now(timezone.utc)).timestamp() * 1000)}",
        framework="playwright",
        suite=suite.get("title", ""),
        environment=default_env,
        branch=default_branch,
        commit_sha=default_commit,
        started_at=started,
        completed_at=_parse_dt(data.get("endTime")) or started,
        report_location=data.get("report_location", ""),
        results=results,
    )


def _walk_tests(suite: dict[str, Any]):
    for child in suite.get("suites", []):
        yield from _walk_tests(child)
    for spec in suite.get("specs", []):
        for test in spec.get("tests", []):
            yield {
                "title": spec.get("title", ""),
                "fullTitle": spec.get("title", ""),
                "status": test.get("status", ""),
                "duration": spec.get("duration") or test.get("duration") or 0,
                "errors": test.get("errors", []),
                "attachments": test.get("attachments", []),
            }


def parse_junit_xml(xml_text: str, *, framework: str, default_env: str = "qa",
                    default_branch: str = "", default_commit: str = "") -> CanonicalTestRun:
    root = ET.fromstring(xml_text)
    started = _parse_dt(root.get("timestamp"))
    results: list[CanonicalTestResult] = []
    for suite_el in _iter_suites(root):
        for case in suite_el.findall("testcase"):
            failures = case.findall("failure")
            errors = case.findall("error")
            skipped = case.findall("skipped")
            if failures:
                status = TestStatus.FAILED
                f = failures[0]
                error, stack = f.get("message", "")[:2000], (f.text or "")[:4000]
            elif errors:
                status = TestStatus.ERROR
                e = errors[0]
                error, stack = e.get("message", "")[:2000], (e.text or "")[:4000]
            elif skipped:
                status = TestStatus.SKIPPED
                error, stack = "", ""
            else:
                status = TestStatus.PASSED
                error, stack = "", ""
            results.append(
                CanonicalTestResult(
                    title=case.get("name", ""),
                    status=status,
                    duration_ms=int(float(case.get("time") or 0) * 1000),
                    error=error,
                    stack_trace=stack,
                    suite=suite_el.get("name", ""),
                )
            )
    return CanonicalTestRun(
        test_run_id=f"{framework}-{int((started or datetime.now(timezone.utc)).timestamp() * 1000)}",
        framework=framework,
        suite=root.get("name", ""),
        environment=default_env,
        branch=default_branch,
        commit_sha=default_commit,
        started_at=started,
        completed_at=None,
        report_location="",
        results=results,
    )


def _iter_suites(root: ET.Element):
    if root.tag == "testsuites":
        for suite in root.findall("testsuite"):
            yield suite
    else:
        yield root


def parse_canonical(data: dict[str, Any]) -> CanonicalTestRun:
    return CanonicalTestRun.model_validate(data)


PARSERS = {
    "playwright": lambda d, **kw: parse_playwright_json(d, **kw),
    "junit": lambda d, **kw: parse_junit_xml(d, **kw),
    "pytest": lambda d, **kw: parse_junit_xml(d, **kw),
    "canonical": parse_canonical,
}
