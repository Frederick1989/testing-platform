"""Demo data seeding and deterministic test-run simulation.

Demo endpoints are gated by APP_ENV. All data here is fictitious and produced
deterministically (seeded RNG) so dashboards/reports are reproducible.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import DefectState, Severity, TestStatus
from app.models.azure import Iteration, WorkItem
from app.models.test import (
    AcceptanceCriterion,
    Defect,
    TestCase,
    TestImplementation,
    TestResult,
    TestRun,
    TestScenario,
)
from app.repositories import azure as az_repo
from app.repositories import tests as test_repo

_DEMO_ITERATIONS = [
    ("Sprint 01", datetime(2026, 1, 5, tzinfo=timezone.utc), datetime(2026, 1, 18, tzinfo=timezone.utc)),
    ("Sprint 02", datetime(2026, 1, 19, tzinfo=timezone.utc), datetime(2026, 2, 1, tzinfo=timezone.utc)),
    ("Sprint 03", datetime(2026, 2, 2, tzinfo=timezone.utc), datetime(2026, 2, 15, tzinfo=timezone.utc)),
    ("Current", datetime(2026, 2, 16, tzinfo=timezone.utc), datetime(2026, 3, 1, tzinfo=timezone.utc)),
]

_DEMO_STORIES = [
    {
        "azure_id": 1234,
        "type": "User Story",
        "title": "Check Weather for a City",
        "description": "As a user I can query the weather for a city through the weather API.",
        "ac": [
            "Given a valid city, when the weather endpoint is called, then the API returns weather information",
            "Given an invalid city, when the API is called, then an appropriate error is returned",
            "Given valid weather data, then required response fields must exist",
        ],
        "state": "Done",
        "iteration": "Sprint 03",
        "assigned": "Ada Lovelace",
        "automation_status": "Automated",
    },
    {
        "azure_id": 1235,
        "type": "User Story",
        "title": "Display Weather Information",
        "description": "As a user I can enter a city and see its weather on the web app.",
        "ac": [
            "User can enter a city",
            "The application displays weather information",
            "Invalid cities display an error",
            "The application remains usable after an invalid search",
        ],
        "state": "Active",
        "iteration": "Current",
        "assigned": "Grace Hopper",
        "automation_status": "Automated",
    },
    {
        "azure_id": 1236,
        "type": "User Story",
        "title": "Show Weather Forecast for the Next 5 Days",
        "description": "As a user I can see a 5-day forecast in the web application.",
        "ac": [
            "The application shows a 5-day forecast",
            "Forecast loads for a valid city",
        ],
        "state": "New",
        "iteration": "Current",
        "assigned": "Ada Lovelace",
        "automation_status": "Not Automated",
    },
    {
        "azure_id": 1237,
        "type": "Task",
        "title": "Set up weather API in Docker Compose",
        "description": "Containerize the mock weather service.",
        "ac": [],
        "state": "Done",
        "iteration": "Sprint 02",
        "assigned": "Linus Torvalds",
        "automation_status": "Not Automated",
    },
    {
        "azure_id": 1238,
        "type": "User Story",
        "title": "Environment setup for staging",
        "description": "Provision and maintain the staging environment (no test output delivered).",
        "ac": [],
        "state": "Active",
        "iteration": "Current",
        "assigned": "Margaret Hamilton",
        "automation_status": "Not Automated",
        "acceptance_test_required": False,
    },
]

_DEMO_DEFECTS = [
    {"azure_id": 2001, "title": "Weather endpoint returns 500 for empty city name",
     "severity": Severity.HIGH, "state": DefectState.ACTIVE, "story": 1234,
     "created_days_ago": 12, "resolved_days_ago": None},
    {"azure_id": 2002, "title": "UI does not clear previous weather after invalid search",
     "severity": Severity.MEDIUM, "state": DefectState.ACTIVE, "story": 1235,
     "created_days_ago": 6, "resolved_days_ago": None},
    {"azure_id": 2003, "title": "Temperatures displayed in wrong units",
     "severity": Severity.CRITICAL, "state": DefectState.NEW, "story": 1235,
     "created_days_ago": 2, "resolved_days_ago": None},
    {"azure_id": 2004, "title": "City name with accents returns 404",
     "severity": Severity.LOW, "state": DefectState.RESOLVED, "story": 1234,
     "created_days_ago": 20, "resolved_days_ago": 5},
    {"azure_id": 2005, "title": "Forecast API times out after 10 seconds",
     "severity": Severity.HIGH, "state": DefectState.CLOSED, "story": 1236,
     "created_days_ago": 30, "resolved_days_ago": 22, "reopened": 1},
    {"azure_id": 2006, "title": "Login returns 500 after password reset",
     "severity": Severity.LOW, "state": DefectState.RESOLVED, "story": 1234,
     "created_days_ago": 3, "resolved_days_ago": 1.5},
]

_TCS = [
    # (key, title, framework, suggested_framework, story_azure, ac_index, flaky)
    ("TC-001", "Weather endpoint returns weather for a valid city", "pytest", "api", 1234, 0, False),
    ("TC-002", "Weather endpoint returns 404 for invalid city", "pytest", "api", 1234, 1, False),
    ("TC-003", "Weather endpoint returns 400 when city parameter missing", "pytest", "api", 1234, 1, False),
    ("TC-004", "Weather response contains required fields", "pytest", "api", 1234, 2, False),
    ("TC-005", "User can search for a city and see weather", "playwright", "ui", 1235, 0, False),
    ("TC-006", "Invalid city displays an error message", "playwright", "ui", 1235, 2, False),
    ("TC-007", "Application remains usable after invalid search", "playwright", "ui", 1235, 3, True),
    ("TC-008", "Web app shows 5-day forecast", "playwright", "ui", 1236, 0, False),
    ("TC-009", "Forecast loads for a valid city", "playwright", "ui", 1236, 1, False),
]

_IMPLS = {
    "TC-001": "tests/test_weather.py::test_valid_city",
    "TC-002": "tests/test_weather.py::test_invalid_city",
    "TC-003": "tests/test_weather.py::test_missing_parameter",
    "TC-004": "tests/test_weather.py::test_response_schema",
    "TC-005": "tests/weather/search.spec.ts::search valid city",
    "TC-006": "tests/weather/search.spec.ts::invalid city error",
    "TC-007": "tests/weather/search.spec.ts::usable after invalid search",
    "TC-008": "tests/weather/forecast.spec.ts::shows 5-day forecast",
    "TC-009": "tests/weather/forecast.spec.ts::forecast loads for valid city",
}


def _utc_ago(days: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


async def seed_demo_data(session: Session, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    # reset existing demo markers to keep seeding idempotent-ish (dev convenience)
    now = datetime.now(timezone.utc)

    iterations: dict[str, Iteration] = {}
    for name, start, finish in _DEMO_ITERATIONS:
        iteration = az_repo.get_iteration_by_name(session, name)
        if iteration is None:
            iteration = Iteration(
                azure_id=name.lower().replace(" ", "-"),
                name=name,
                path=f"Demo\\{name}",
                state="Current" if name == "Current" else "Closed",
                start_date=start,
                finish_date=finish,
                is_current=(name == "Current"),
                url="",
                last_synced_at=now,
            )
            session.add(iteration)
            session.flush()
        iterations[name] = iteration

    stories: dict[int, WorkItem] = {}
    for story_data in _DEMO_STORIES:
        story = az_repo.get_work_item_by_azure_id(session, story_data["azure_id"])
        if story is None:
            story = WorkItem(
                azure_id=story_data["azure_id"], type=story_data["type"],
                title=story_data["title"], description=story_data["description"],
                acceptance_criteria_raw="\n".join(story_data["ac"]),
                state=story_data["state"], assigned_to=story_data["assigned"],
                area_path="Demo\\Weather",
                tags=list(story_data.get("tags", ["demo"])),
                automation_status=story_data.get("automation_status", ""),
                acceptance_test_required=story_data.get("acceptance_test_required", True),
                created_at=_utc_ago(45), updated_at=now, url="", last_synced_at=now,
            )
            session.add(story)
            session.flush()
            story.iteration_id = iterations[story_data["iteration"]].id
            story.iteration_name = story_data["iteration"]
        else:
            # keep demo deterministic on re-seed: refresh classification fields
            story.automation_status = story_data.get("automation_status", "")
            story.acceptance_test_required = story_data.get("acceptance_test_required", True)
            story.tags = list(story_data.get("tags", ["demo"]))
        stories[story_data["azure_id"]] = story

    # acceptance criteria
    for story_data in _DEMO_STORIES:
        story = stories[story_data["azure_id"]]
        if not [ac for ac in story.acceptance_criteria if ac.is_active]:
            az_repo.upsert_acceptance_criteria(session, story.id, story_data["ac"])

    # test cases + links + implementations
    for key, title, framework, suggested, story_azure, ac_idx, is_flaky in _TCS:
        tc = test_repo.get_test_case(session, key)
        if tc is None:
            tc = test_repo.create_test_case(
                session, key=key, title=title,
                description=f"Demo test case for story {story_azure}.",
                priority="HIGH" if is_flaky else "MEDIUM",
                suggested_framework=suggested, source="demo",
            )
            session.flush()
            scenario = TestScenario(
                test_case_id=tc.id, name=f"{title} - primary", description=title,
                steps=[], status="active", created_at=now,
            )
            session.add(scenario)
            session.flush()
            impl_path = _IMPLS.get(key, f"tests/{key}.py")
            test_repo.create_implementation(
                session, test_case_id=tc.id, framework=framework,
                path=impl_path, name=title, content_hash=f"demo-{key}",
            )
        story = stories[story_azure]
        acs = list(
            session.scalars(
                select(AcceptanceCriterion)
                .where(
                    AcceptanceCriterion.work_item_id == story.id,
                    AcceptanceCriterion.is_active.is_(True),
                )
                .order_by(AcceptanceCriterion.sort_order)
            )
        )
        ac_id = acs[ac_idx].id if ac_idx < len(acs) else None
        existing = test_repo.story_link_map(session, story.id)
        if tc.id not in existing.get(ac_id if ac_id is not None else -1, []):
            test_repo.link_story(
                session, work_item_id=story.id, test_case_id=tc.id,
                acceptance_criterion_id=ac_id, rationale="demo seed",
            )
        if ac_id is not None:
            acs[ac_idx].status = "COVERED"

    # defects
    for d in _DEMO_DEFECTS:
        row = session.scalar(
            select(Defect).where(Defect.azure_id == d["azure_id"])
        )
        if row is None:
            row = Defect(
                azure_id=d["azure_id"], title=d["title"],
                severity=d["severity"].value, state=d["state"].value,
                story_work_item_id=d["story"],
                created_at=_utc_ago(d["created_days_ago"]),
                resolved_at=_utc_ago(d["resolved_days_ago"]) if d["resolved_days_ago"] else None,
                closed_at=_utc_ago(d["resolved_days_ago"]) if d["resolved_days_ago"] else None,
                reopened_count=d.get("reopened", 0),
                tags=["demo"], url="", last_synced_at=now,
            )
            session.add(row)

    from app.config import settings
    from app.repositories import jobs as jobs_repo

    for name, schedule in (
        ("azure-sync", settings.schedule_azure_sync),
        ("execution-runner", settings.schedule_test_execution),
        ("nightly-regression", settings.schedule_nightly_regression),
        ("report-builder", settings.schedule_report_generation),
    ):
        jobs_repo.upsert_agent(session, name=name, schedule=schedule, enabled=True)

    session.commit()
    run_result = await simulate_runs(
        session,
        {"iterations": 14, "failure_rate": 0.12, "flaky_rate": 1.0,
         "framework": "both", "environment": "nightly", "seed": 42},
    )
    session.commit()
    return {
        "stories": len(stories),
        "test_cases": len(_TCS),
        "defects": len(_DEMO_DEFECTS),
        "agents": 4,
        "simulated_runs": run_result.get("runs", 0),
    }


def _active_test_cases(session: Session, framework: str) -> list[TestCase]:
    frameworks = []
    if framework in ("api", "pytest"):
        frameworks = ["pytest"]
    elif framework in ("ui", "web", "playwright"):
        frameworks = ["playwright"]
    else:
        frameworks = ["pytest", "playwright"]
    from sqlalchemy import select

    rows = session.execute(
        select(TestCase)
        .join(TestImplementation, TestImplementation.test_case_id == TestCase.id)
        .where(TestCase.status == "active",
               TestImplementation.framework.in_(frameworks))
    ).scalars().all()
    return list({tc.id: tc for tc in rows}.values())


async def simulate_runs(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    iterations = int(params.get("iterations", 10))
    failure_rate = float(params.get("failure_rate", 0.1))
    flaky_rate = float(params.get("flaky_rate", 0.5))
    framework = params.get("framework", "both")
    environment = params.get("environment", "qa")
    seed = int(params.get("seed", 42))

    tcs = _active_test_cases(session, framework)
    if not tcs:
        return {"runs": 0, "test_cases": 0}

    runs_created = 0
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d%H%M%S")
    for i in range(iterations):
        rng = random.Random(seed + i)
        started = now - timedelta(days=iterations - i, hours=rng.randint(0, 5))
        run = TestRun(
            run_id=f"demo-run-{seed}-{stamp}-{i}",
            framework=framework,
            environment=environment,
            branch="develop",
            commit_sha=f"abc123{i:04x}",
            started_at=started,
            created_at=started,
        )
        session.add(run)
        session.flush()
        total = passed = failed = skipped = flaky_count = errors = 0
        for tc in tcs:
            status = _outcome(rng, tc, failure_rate, flaky_rate)
            total += 1
            if status == TestStatus.PASSED:
                passed += 1
            elif status == TestStatus.FAILED:
                failed += 1
            elif status == TestStatus.FLAKY:
                flaky_count += 1
            elif status == TestStatus.ERROR:
                errors += 1
            else:
                skipped += 1
            session.add(
                TestResult(
                    test_run_id=run.id, test_case_id=tc.id,
                    framework=run.framework, suite="demo", title=tc.title,
                    status=status.value,
                    duration_ms=rng.randint(80, 2500),
                    environment=environment, branch="develop",
                    commit_sha=run.commit_sha,
                    started_at=started + timedelta(seconds=rng.randint(1, 60)),
                    completed_at=started + timedelta(seconds=rng.randint(60, 120)),
                    error="simulated failure" if status == TestStatus.FAILED else "",
                    stack_trace="simulated stack (demo)" if status == TestStatus.FAILED else "",
                    artifacts=[], is_flaky=status == TestStatus.FLAKY,
                )
            )
        run.total, run.passed, run.failed = total, passed, failed
        run.skipped, run.flaky, run.error_count = skipped, flaky_count, errors
        run.completed_at = started + timedelta(minutes=1)
        run.duration_ms = (run.completed_at - started).seconds * 1000
        run.status = "COMPLETED"
        runs_created += 1
    session.commit()
    return {"runs": runs_created, "test_cases": len(tcs), "seed": seed}


def _outcome(rng: random.Random, tc: TestCase, failure_rate: float,
             flaky_rate: float) -> TestStatus:
    is_flaky = tc.key == "TC-007"
    if is_flaky:
        return TestStatus.FLAKY if rng.random() < flaky_rate else TestStatus.PASSED
    if tc.key in ("TC-002", "TC-006"):
        # intentionally failing tests in the demo
        roll = rng.random()
        if roll < failure_rate * 0.5:
            return TestStatus.PASSED
        return TestStatus.FAILED if roll < failure_rate * 2 else TestStatus.PASSED
    if tc.key == "TC-003":
        # mostly passing with occasional error
        return TestStatus.ERROR if rng.random() < failure_rate * 0.3 else TestStatus.PASSED
    roll = rng.random()
    if roll < failure_rate:
        return TestStatus.FAILED
    if roll < failure_rate + 0.01:
        return TestStatus.SKIPPED
    return TestStatus.PASSED
