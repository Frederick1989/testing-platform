"""Test matrix assembly: story -> AC -> test case -> scenario -> impl -> results."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.test import Defect, TestResult
from app.repositories import tests as test_repo
from app.services.readiness import evaluate_story


def _result_out(r: TestResult) -> dict[str, Any] | None:
    if r is None:
        return None
    return {
        "id": r.id, "title": r.title, "status": r.status,
        "duration_ms": r.duration_ms, "environment": r.environment,
        "branch": r.branch, "commit_sha": r.commit_sha,
        "started_at": r.started_at, "error": r.error,
        "artifacts": r.artifacts, "is_flaky": r.is_flaky,
    }


def build_matrix(session: Session, work_item_pk: int) -> dict[str, Any]:
    from app.models.azure import WorkItem

    story = session.get(WorkItem, work_item_pk)
    return _build(session, story)


def _build(session: Session, story: Any) -> dict[str, Any]:
    if story is None:
        raise ValueError("story not found")

    acs = [ac for ac in story.acceptance_criteria if ac.is_active]
    acs.sort(key=lambda a: a.sort_order)
    links = test_repo.get_story_links(session, story.id)

    # latest + previous result per test case
    def results_for(tc_id: int) -> tuple[TestResult | None, TestResult | None]:
        rs = test_repo.latest_test_results(session, tc_id, limit=2)
        if not rs:
            return None, None
        return rs[0], rs[1] if len(rs) > 1 else None

    ac_nodes = []
    for ac in acs:
        ac_links = [link for link in links if link.acceptance_criterion_id == ac.id]
        test_nodes = []
        for link in ac_links:
            tc = link.test_case
            latest, previous = results_for(tc.id)
            scenarios = [
                {"id": s.id, "name": s.name} for s in test_repo.list_scenarios(session, tc.id)
            ]
            implementations = [
                {"id": i.id, "framework": i.framework, "path": i.path}
                for i in test_repo.list_implementations(session, tc.id)
            ]
            test_nodes.append(
                {
                    "id": tc.id,
                    "key": tc.key,
                    "title": tc.title,
                    "status": tc.status,
                    "scenarios": scenarios,
                    "implementations": implementations,
                    "latest": _result_out(latest),
                    "previous": _result_out(previous),
                }
            )
        ac_nodes.append(
            {
                "id": ac.id,
                "text": ac.text,
                "status": ac.status,
                "sort_order": ac.sort_order,
                "test_cases": test_nodes,
            }
        )

    defects = list(
        session.scalars(
            select(Defect).where(Defect.story_work_item_id == story.azure_id)
        )
    )
    readiness = evaluate_story(session, story.id)

    return {
        "work_item_id": story.id,
        "azure_id": story.azure_id,
        "title": story.title,
        "url": story.url,
        "state": story.state,
        "iteration_name": story.iteration_name,
        "type": story.type,
        "acceptance_criteria": ac_nodes,
        "defects": [
            {"id": d.id, "azure_id": d.azure_id, "title": d.title,
             "severity": d.severity, "state": d.state, "url": d.url}
            for d in defects
        ],
        "readiness": readiness,
        "coverage": round(
            sum(1 for a in ac_nodes if a["status"] in ("COVERED", "PARTIALLY_COVERED"))
            / max(len(ac_nodes), 1) * 100,
            1,
        ),
    }


def matrix_for_sprint(session: Session, iteration_name: str | None = None) -> list[dict[str, Any]]:
    from app.models.azure import WorkItem

    stmt = select(WorkItem).where(
        WorkItem.type == "User Story", WorkItem.is_active.is_(True)
    )
    if iteration_name:
        stmt = stmt.where(WorkItem.iteration_name == iteration_name)
    stories = session.scalars(stmt.order_by(WorkItem.azure_id)).all()
    return [_build(session, s) for s in stories]
