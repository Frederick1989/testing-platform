"""Agent definitions and the scheduled-job registry.

Each agent is a plain async function; scheduled agents enqueue jobs. LLM is not
used where a scheduled job is sufficient.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.core.types import JobType

logger = logging.getLogger("app.agents")


async def azure_sync_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    from app.adapters.azure.client import make_client
    from app.services.sync import sync_all

    client = make_client()
    counts = await sync_all(session, client)
    return counts


async def azure_sync_work_items_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    from app.adapters.azure.client import make_client
    from app.services.sync import sync_work_items

    client = make_client()
    count = await sync_work_items(session, client, only=params.get("types"))
    session.commit()
    return {"work_items": count}


async def azure_sync_pr_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    from app.adapters.azure.client import make_client
    from app.services.sync import sync_pull_requests

    count = await sync_pull_requests(session, make_client())
    session.commit()
    return {"pull_requests": count}


async def azure_sync_iterations_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    from app.adapters.azure.client import make_client
    from app.services.sync import sync_iterations

    count = await sync_iterations(session, make_client())
    session.commit()
    return {"iterations": count}


async def test_matrix_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    from app.services.intelligence import run_test_matrix_analysis

    return await run_test_matrix_analysis(session, params["work_item_id"])


async def test_generation_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    from app.services.intelligence import run_test_generation

    return await run_test_generation(session, params["work_item_id"])


async def _call_runner(url: str, endpoint: str, payload: dict[str, Any],
                       timeout: float = 300) -> dict[str, Any] | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{url}{endpoint}", json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("runner %s unreachable: %s", url, exc)
        return None


async def test_execution_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    frameworks = params.get("framework", "both")
    environment = params.get("environment", "qa")
    results: dict[str, Any] = {}
    if frameworks in ("api", "both") and settings.api_runner_url:
        results["api"] = await _call_runner(
            settings.api_runner_url, "/execute",
            {"environment": environment, "branch": params.get("branch", "develop"),
             "commit_sha": params.get("commit_sha", "")},
        )
    if frameworks in ("ui", "web", "both") and settings.web_runner_url:
        results["web"] = await _call_runner(
            settings.web_runner_url, "/execute",
            {"environment": environment, "branch": params.get("branch", "develop"),
             "commit_sha": params.get("commit_sha", "")},
        )
    return {"triggered": results}


async def nightly_regression_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    await test_execution_agent(session, {"framework": "both", "environment": "nightly"})
    from app.services import flakiness as flakiness_svc
    from app.core.events import DomainEvent, bus
    from app.core.types import NotificationType

    regression = flakiness_svc.regression_report(session)
    await bus.publish(
        DomainEvent(
            NotificationType.NIGHTLY_REGRESSION.value,
            {
                "run_id": "nightly",
                "new_failures": regression["counts"]["new_failures"],
                "repeated": regression["counts"]["repeated_failures"],
            },
        )
    )
    return regression["counts"]


async def report_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    from app.services.reports import generate_report

    result = generate_report(session, sprint=params.get("sprint", ""))
    return {"archive_id": result["archive_id"], "pdf": result["pdf_path"]}


async def demo_run_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    from app.services.demo import simulate_runs

    return await simulate_runs(session, params)


async def demo_seed_agent(session: Session, params: dict[str, Any]) -> dict[str, Any]:
    from app.services.demo import seed_demo_data

    return await seed_demo_data(session, params)


def build_registry() -> dict[str, Any]:
    return {
        JobType.AZURE_SYNC.value: azure_sync_agent,
        JobType.AZURE_SYNC_WORK_ITEMS.value: azure_sync_work_items_agent,
        JobType.AZURE_SYNC_PR.value: azure_sync_pr_agent,
        JobType.AZURE_SYNC_ITERATIONS.value: azure_sync_iterations_agent,
        JobType.TEST_MATRIX_ANALYSIS.value: test_matrix_agent,
        JobType.TEST_GENERATION.value: test_generation_agent,
        JobType.TEST_EXECUTION.value: test_execution_agent,
        JobType.NIGHTLY_REGRESSION.value: nightly_regression_agent,
        JobType.REPORT_GENERATION.value: report_agent,
        JobType.DEMO_RUN.value: demo_run_agent,
        JobType.DEMO_SEED.value: demo_seed_agent,
    }
