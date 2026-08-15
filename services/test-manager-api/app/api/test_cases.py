"""Test cases, scenarios, implementations, story links."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db
from app.core.auth import require_token
from app.core.errors import BadRequestError, NotFoundError
from app.repositories import azure as az_repo
from app.repositories import tests as test_repo
from app.schemas.tests import LinkRequest, ScenarioCreate, TestCaseCreate, TestCaseOut, TestCaseUpdate

router = APIRouter(prefix="/test-cases", tags=["test-cases"])


@router.get("")
def list_test_cases(
    session: Annotated[Session, Depends(db)],
    story_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    items, total = test_repo.list_test_cases(
        session, story_id=story_id, status=status, page=page, page_size=page_size
    )
    out = []
    for tc in items:
        links = test_repo.get_story_links(session, -1) if False else _links_for_test_case(session, tc.id)
        out.append(
            TestCaseOut(
                id=tc.id, key=tc.key, title=tc.title, description=tc.description,
                priority=tc.priority, suggested_framework=tc.suggested_framework,
                status=tc.status, source=tc.source,
                created_at=tc.created_at, updated_at=tc.updated_at,
                linked_story_ids=links["stories"], linked_ac_ids=links["acs"],
            )
        )
    return {"items": [o.model_dump() for o in out], "total": total, "page": page, "page_size": page_size}


def _links_for_test_case(session: Session, test_case_id: int) -> dict:
    from sqlalchemy import select

    from app.models.test import TestStoryLink

    links = session.scalars(
        select(TestStoryLink).where(TestStoryLink.test_case_id == test_case_id)
    ).all()
    return {
        "stories": list({link.work_item_id for link in links}),
        "acs": list({link.acceptance_criterion_id for link in links if link.acceptance_criterion_id}),
    }


@router.post("", status_code=201)
async def create_test_case(
    body: TestCaseCreate,
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    key = body.key or test_repo.next_test_case_key(session)
    if test_repo.get_test_case(session, key):
        raise BadRequestError(f"test case {key} already exists")
    tc = test_repo.create_test_case(
        session, key=key, title=body.title, description=body.description,
        priority=body.priority, suggested_framework=body.suggested_framework,
        source="manual",
    )
    session.commit()
    return {"key": tc.key, "id": tc.id}


@router.get("/{key}")
def get_test_case(
    key: str,
    session: Annotated[Session, Depends(db)],
) -> dict:
    tc = test_repo.get_test_case(session, key)
    if tc is None:
        raise NotFoundError(f"test case {key} not found")
    links = _links_for_test_case(session, tc.id)
    return {
        "id": tc.id, "key": tc.key, "title": tc.title, "description": tc.description,
        "priority": tc.priority, "suggested_framework": tc.suggested_framework,
        "status": tc.status, "source": tc.source,
        "scenarios": [{"id": s.id, "name": s.name, "steps": s.steps}
                      for s in test_repo.list_scenarios(session, tc.id)],
        "implementations": [{"id": i.id, "framework": i.framework, "path": i.path}
                            for i in test_repo.list_implementations(session, tc.id)],
        "linked_story_ids": links["stories"], "linked_ac_ids": links["acs"],
    }


@router.put("/{key}")
async def update_test_case(
    key: str,
    body: TestCaseUpdate,
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    tc = test_repo.get_test_case(session, key)
    if tc is None:
        raise NotFoundError(f"test case {key} not found")
    for field in ("title", "description", "priority", "suggested_framework", "status"):
        value = getattr(body, field)
        if value is not None:
            setattr(tc, field, value)
    tc.updated_at = datetime.now(timezone.utc)
    session.commit()
    return {"key": tc.key, "status": "UPDATED"}


@router.post("/{key}/scenarios", status_code=201)
async def add_scenario(
    key: str,
    body: ScenarioCreate,
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    tc = test_repo.get_test_case(session, key)
    if tc is None:
        raise NotFoundError(f"test case {key} not found")
    from app.models.test import TestScenario

    scenario = TestScenario(
        test_case_id=tc.id, name=body.name, description=body.description,
        steps=body.steps, status="active",
        created_at=datetime.now(timezone.utc),
    )
    session.add(scenario)
    session.commit()
    return {"id": scenario.id, "status": "CREATED"}


@router.post("/link", status_code=201)
async def link_to_story(
    body: LinkRequest,
    _: Annotated[str, Depends(require_token)],
    session: Annotated[Session, Depends(db)],
) -> dict:
    story = az_repo.resolve_work_item(session, body.work_item_id)
    if story is None:
        raise NotFoundError(f"work item {body.work_item_id} not found (run azure sync first)")
    tc = test_repo.get_test_case(session, body.test_case_key)
    if tc is None:
        raise NotFoundError(f"test case {body.test_case_key} not found")
    ac_id = None
    if body.acceptance_criterion_index is not None:
        acs = [ac for ac in story.acceptance_criteria if ac.is_active]
        acs.sort(key=lambda a: a.sort_order)
        if body.acceptance_criterion_index >= len(acs):
            raise BadRequestError("acceptance_criterion_index out of range")
        ac = acs[body.acceptance_criterion_index]
        ac.status = "COVERED"
        ac_id = ac.id
    link = test_repo.link_story(
        session, work_item_id=story.id, test_case_id=tc.id,
        acceptance_criterion_id=ac_id, rationale=body.rationale,
    )
    session.commit()
    return {"link_id": link.id, "status": "LINKED"}
