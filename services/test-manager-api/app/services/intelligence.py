"""AI-augmented workflows: test-matrix analysis and test generation.

The LLM never writes to the database. Services validate structured output,
merge it with deterministic data, and persist only validated results.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.llm.base import LLMProvider
from app.adapters.llm.factory import build_provider, describe
from app.core.errors import BadRequestError, NotFoundError
from app.core.events import DomainEvent, bus
from app.core.types import NotificationType
from app.models.analysis import TestGenerationCandidate, TestMatrixAnalysis
from app.repositories import azure as az_repo
from app.repositories import tests as test_repo

logger = logging.getLogger("app.intelligence")


def _collect_story_input(session: Session, work_item_id: int) -> dict[str, Any]:
    from app.models.azure import WorkItem

    story = session.get(WorkItem, work_item_id)
    if story is None:
        raise NotFoundError(f"work item {work_item_id} not found")

    acs = [ac for ac in story.acceptance_criteria if ac.is_active]
    acs.sort(key=lambda a: a.sort_order)
    links = test_repo.get_story_links(session, story.id)
    by_ac: dict[int, list[str]] = {}
    existing_keys: list[str] = []
    for link in links:
        tc = link.test_case
        if tc is None:
            continue
        existing_keys.append(tc.key)
        key = link.acceptance_criterion_id or -1
        by_ac.setdefault(key, []).append(tc.key)

    history: list[dict[str, Any]] = []
    for key in existing_keys:
        tc = test_repo.get_test_case(session, key)
        if tc is None:
            continue
        for r in test_repo.latest_test_results(session, tc.id, limit=5):
            history.append(
                {"test_case": key, "status": r.status, "started_at": r.started_at}
            )

    recent_prs = [
        {"title": p.title, "status": p.status, "repo": p.repo}
        for p in az_repo.list_pull_requests(session, limit=10)
    ]

    return {
        "story_id": story.azure_id,
        "title": story.title,
        "description": story.description[:4000],
        "state": story.state,
        "iteration": story.iteration_name,
        "acceptance_criteria": [ac.text for ac in acs],
        "linked_tests_by_ac": [by_ac.get(ac.id, []) for ac in acs],
        "existing_test_keys": existing_keys,
        "test_history": history[:50],
        "recent_pull_requests": recent_prs,
        "tags": story.tags,
    }


async def run_test_matrix_analysis(
    session: Session, work_item_id: int, *, force: bool = False
) -> dict[str, Any]:
    from app.models.azure import WorkItem

    story = session.get(WorkItem, work_item_id)
    if story is None:
        raise NotFoundError(f"work item {work_item_id} not found")

    acs = [ac for ac in story.acceptance_criteria if ac.is_active]
    acs.sort(key=lambda a: a.sort_order)
    links = test_repo.get_story_links(session, work_item_id)

    # deterministic coverage facts
    by_ac: dict[int, set[int]] = {}
    for link in links:
        key = link.acceptance_criterion_id or -1
        by_ac.setdefault(key, set()).add(link.test_case_id)
    covered_count = sum(1 for ac in acs if by_ac.get(ac.id))
    coverage_pct = round(covered_count / max(len(acs), 1) * 100, 1)

    story_input = _collect_story_input(session, work_item_id)
    provider: LLMProvider = build_provider()
    analysis = await provider.analyze_story(story_input)

    # merge deterministic facts (never let the model report numbers the DB doesn't support)
    analysis.coverage_pct = coverage_pct
    deterministic_status = (
        "COVERED" if coverage_pct == 100 and acs else
        ("NOT_COVERED" if coverage_pct == 0 and acs else "PARTIALLY_COVERED")
    )
    if analysis.status == "REVIEW_REQUIRED" or deterministic_status != "COVERED":
        final_status = analysis.status if analysis.status == "REVIEW_REQUIRED" else (
            "REVIEW_REQUIRED" if analysis.new_tests else deterministic_status
        )
    else:
        final_status = "COVERED"

    now = datetime.now(timezone.utc)
    row = TestMatrixAnalysis(
        work_item_id=work_item_id,
        coverage_pct=coverage_pct,
        missing_ac_count=len(acs) - covered_count,
        existing_tests_reused=len(analysis.reuse),
        new_tests_required=len(analysis.new_tests),
        potentially_redundant_tests=len(analysis.redundant),
        status=final_status,
        is_new_functionality=analysis.is_new_functionality,
        details=analysis.model_dump(),
        model=describe(provider).get("implementation", ""),
        generated_at=now,
    )
    session.add(row)
    session.flush()

    # update AC coverage status from deterministic links
    for ac in acs:
        ac.status = "COVERED" if by_ac.get(ac.id) else "NOT_COVERED"

    # persist proposed candidates (never directly activate test cases)
    candidates = []
    for proposed in analysis.new_tests:
        ac_index = proposed.acceptance_criterion_index
        ac_id = acs[ac_index].id if ac_index is not None and ac_index < len(acs) else None
        candidates.append(
            TestGenerationCandidate(
                work_item_id=work_item_id,
                analysis_id=row.id,
                title=proposed.title,
                acceptance_criterion_id=ac_id,
                framework=proposed.framework,
                scenario=proposed.scenario,
                expected=proposed.expected,
                status="proposed",
                created_at=now,
            )
        )
    session.add_all(candidates)
    session.commit()

    missing = len(acs) - covered_count
    if missing > 0:
        await bus.publish(
            DomainEvent(
                NotificationType.COVERAGE_GAP.value,
                {"work_item_id": work_item_id, "azure_id": story.azure_id,
                 "title": story.title, "missing": missing},
            )
        )

    return {
        "story_id": story.azure_id,
        "coverage": coverage_pct,
        "missing_acceptance_criteria": missing,
        "existing_tests_reused": len(analysis.reuse),
        "new_tests_required": len(analysis.new_tests),
        "potentially_redundant_tests": len(analysis.redundant),
        "status": final_status,
        "analysis_id": row.id,
        "model": describe(provider).get("implementation", ""),
    }


async def run_test_generation(session: Session, work_item_id: int) -> dict[str, Any]:
    from app.adapters.git import GitService
    from app.models.azure import WorkItem

    story = session.get(WorkItem, work_item_id)
    if story is None:
        raise NotFoundError(f"work item {work_item_id} not found")

    candidates = list(
        session.scalars(
            select(TestGenerationCandidate)
            .where(
                TestGenerationCandidate.work_item_id == work_item_id,
                TestGenerationCandidate.status.in_(["proposed", "approved"]),
            )
            .order_by(TestGenerationCandidate.id)
        )
    )
    if not candidates:
        raise BadRequestError(
            "no proposed test candidates for this story; run sync-test-matrix first"
        )

    request = {
        "story_id": story.azure_id,
        "story_title": story.title,
        "candidates": [
            {
                "title": c.title,
                "framework": c.framework,
                "scenario": c.scenario,
                "expected": c.expected,
            }
            for c in candidates
        ],
    }
    provider: LLMProvider = build_provider()
    generated = await provider.generate_test_cases(request)

    git = GitService()
    branch = f"test/story-{story.azure_id}-generated-tests"
    git.create_branch(branch)

    created = 0
    for c, gen in zip(candidates, generated.tests):
        path = git.write_file(gen.path, gen.content)
        tc = test_repo.create_test_case(
            session,
            key=test_repo.next_test_case_key(session),
            title=gen.title or c.title,
            description=f"Generated for story {story.azure_id} ({gen.framework}).\nScenario: {c.scenario}\nExpected: {c.expected}",
            priority="MEDIUM",
            suggested_framework="api" if gen.framework == "api" else "ui",
            source="generated",
        )
        session.flush()
        ac_id = c.acceptance_criterion_id
        test_repo.link_story(
            session,
            work_item_id=work_item_id,
            test_case_id=tc.id,
            acceptance_criterion_id=ac_id,
            rationale=f"Generated test for story {story.azure_id}",
        )
        content_hash = hashlib.sha256(gen.content.encode()).hexdigest()[:16]
        test_repo.create_implementation(
            session,
            test_case_id=tc.id,
            framework="playwright" if gen.framework == "ui" else "pytest",
            path=str(path.relative_to(git.root)),
            name=gen.title,
            content_hash=content_hash,
        )
        c.status = "generated"
        created += 1

    git.commit(f"test(story-{story.azure_id}): generated automated tests")
    pushed = git.push(branch)

    pull_request_url = ""
    if pushed:
        from app.adapters.azure.client import make_client

        client = make_client()
        pr = await client.create_pull_request(
            title=f"[Tests] Generated tests for story {story.azure_id}",
            source_ref=branch,
            target_ref="main",
            description=(
                f"Automated tests generated for story {story.azure_id}: {story.title}.\n"
                f"Files: {created} test file(s) in {branch}.\n"
                "Human review required before merge."
            ),
        )
        pull_request_url = pr.get("url", "")
        await bus.publish(
            DomainEvent(
                NotificationType.PR_CREATED.value,
                {"work_item_id": work_item_id, "story_azure_id": story.azure_id,
                 "pr_url": pull_request_url, "branch": branch},
            )
        )

    session.commit()
    return {
        "job_id": None,
        "story_id": story.azure_id,
        "branch": branch,
        "tests_created": created,
        "test_execution": "PENDING",
        "pull_request_url": pull_request_url,
        "status": "REVIEW_REQUIRED",
    }
