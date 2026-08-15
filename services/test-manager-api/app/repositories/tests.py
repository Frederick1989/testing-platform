"""Data access for test management, execution and defects."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.test import (
    Defect,
    TestCase,
    TestDefectLink,
    TestImplementation,
    TestResult,
    TestRun,
    TestScenario,
    TestStoryLink,
)


def next_test_case_key(session: Session) -> str:
    max_key = session.scalar(select(func.max(TestCase.key)))
    if not max_key:
        return "TC-001"
    try:
        n = int(max_key.split("-")[-1]) + 1
    except ValueError:
        n = len(session.scalars(select(TestCase.key)).all()) + 1
    return f"TC-{n:03d}"


def create_test_case(session: Session, *, key: str, title: str, description: str,
                     priority: str, suggested_framework: str, source: str = "auto") -> TestCase:
    now = datetime.now(timezone.utc)
    tc = TestCase(
        key=key, title=title, description=description, priority=priority,
        suggested_framework=suggested_framework, source=source, status="active",
        created_at=now, updated_at=now,
    )
    session.add(tc)
    return tc


def get_test_case(session: Session, key: str) -> TestCase | None:
    return session.scalar(select(TestCase).where(TestCase.key == key))


def get_test_case_by_id(session: Session, test_case_id: int) -> TestCase | None:
    return session.get(TestCase, test_case_id)


def list_test_cases(session: Session, *, story_id: int | None = None,
                    status: str | None = None, page: int = 1,
                    page_size: int = 100) -> tuple[Sequence[TestCase], int]:
    stmt = select(TestCase)
    if status:
        stmt = stmt.where(TestCase.status == status)
    if story_id:
        linked_ids = session.scalars(
            select(TestStoryLink.test_case_id).where(
                TestStoryLink.work_item_id == story_id
            )
        ).all()
        stmt = stmt.where(TestCase.id.in_(linked_ids))
    total = len(session.execute(stmt.with_only_columns(TestCase.id)).all())
    items = session.scalars(
        stmt.order_by(TestCase.key).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return items, total


def list_scenarios(session: Session, test_case_id: int) -> Sequence[TestScenario]:
    return session.scalars(
        select(TestScenario)
        .where(TestScenario.test_case_id == test_case_id)
        .order_by(TestScenario.id)
    ).all()


def create_implementation(session: Session, *, test_case_id: int, framework: str,
                          path: str, name: str, content_hash: str) -> TestImplementation:
    impl = TestImplementation(
        test_case_id=test_case_id, framework=framework, path=path, name=name,
        status="active", content_hash=content_hash,
    )
    session.add(impl)
    return impl


def get_implementation(session: Session, implementation_id: int) -> TestImplementation | None:
    return session.get(TestImplementation, implementation_id)


def list_implementations(session: Session, test_case_id: int) -> Sequence[TestImplementation]:
    return session.scalars(
        select(TestImplementation).where(TestImplementation.test_case_id == test_case_id)
    ).all()


def link_story(session: Session, *, work_item_id: int, test_case_id: int,
               acceptance_criterion_id: int | None, rationale: str) -> TestStoryLink:
    link = session.scalar(
        select(TestStoryLink).where(
            TestStoryLink.work_item_id == work_item_id,
            TestStoryLink.test_case_id == test_case_id,
            (TestStoryLink.acceptance_criterion_id.is_(None) if acceptance_criterion_id is None
             else TestStoryLink.acceptance_criterion_id == acceptance_criterion_id),
        )
    )
    if link is None:
        link = TestStoryLink(
            work_item_id=work_item_id,
            acceptance_criterion_id=acceptance_criterion_id,
            test_case_id=test_case_id,
            coverage_status="NOT_COVERED",
            rationale=rationale,
            created_at=datetime.now(timezone.utc),
        )
        session.add(link)
    else:
        link.rationale = rationale
    return link


def get_story_links(session: Session, work_item_id: int) -> Sequence[TestStoryLink]:
    return session.scalars(
        select(TestStoryLink).where(TestStoryLink.work_item_id == work_item_id)
    ).all()


def story_link_map(session: Session, work_item_id: int) -> dict[int, list[int]]:
    """map acceptance_criterion_id -> list of test_case_ids"""
    links = get_story_links(session, work_item_id)
    result: dict[int, list[int]] = {}
    for link in links:
        key = link.acceptance_criterion_id or -1
        result.setdefault(key, []).append(link.test_case_id)
    return result


def create_test_run(session: Session, *, run_id: str, framework: str,
                    environment: str, branch: str, commit_sha: str,
                    started_at: datetime | None) -> TestRun:
    run = TestRun(
        run_id=run_id, framework=framework, environment=environment,
        branch=branch, commit_sha=commit_sha, started_at=started_at,
        status="RUNNING", created_at=datetime.now(timezone.utc),
    )
    session.add(run)
    return run


def get_test_run(session: Session, run_id: str) -> TestRun | None:
    return session.scalar(select(TestRun).where(TestRun.run_id == run_id))


def get_test_run_by_id(session: Session, test_run_pk: int) -> TestRun | None:
    return session.get(TestRun, test_run_pk)


def list_test_runs(session: Session, *, framework: str | None = None,
                   environment: str | None = None, limit: int = 50) -> Sequence[TestRun]:
    stmt = select(TestRun)
    if framework:
        stmt = stmt.where(TestRun.framework == framework)
    if environment:
        stmt = stmt.where(TestRun.environment == environment)
    return session.scalars(stmt.order_by(TestRun.created_at.desc()).limit(limit)).all()


def latest_test_results(session: Session, test_case_id: int,
                        limit: int = 2) -> Sequence[TestResult]:
    return session.scalars(
        select(TestResult)
        .where(TestResult.test_case_id == test_case_id)
        .order_by(TestResult.started_at.desc())
        .limit(limit)
    ).all()


def last_run_for_test_case(session: Session, test_case_id: int) -> TestResult | None:
    return session.scalar(
        select(TestResult)
        .where(TestResult.test_case_id == test_case_id)
        .order_by(TestResult.started_at.desc())
        .limit(1)
    )


def list_results(session: Session, *, run_id: int | None = None,
                 status: str | None = None, test_case_key: str | None = None,
                 limit: int = 200, page: int = 1, page_size: int = 50) -> tuple[Sequence[TestResult], int]:
    stmt = select(TestResult)
    if run_id is not None:
        stmt = stmt.where(TestResult.test_run_id == run_id)
    if status:
        stmt = stmt.where(TestResult.status == status)
    if test_case_key:
        tc = get_test_case(session, test_case_key)
        if tc:
            stmt = stmt.where(TestResult.test_case_id == tc.id)
    total = len(session.execute(stmt.with_only_columns(TestResult.id)).all())
    items = session.scalars(
        stmt.order_by(TestResult.started_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return items, total


def get_result(session: Session, result_id: int) -> TestResult | None:
    return session.get(TestResult, result_id)


def list_results_for_run(session: Session, run_pk: int) -> Sequence[TestResult]:
    return session.scalars(
        select(TestResult)
        .where(TestResult.test_run_id == run_pk)
        .order_by(TestResult.title)
    ).all()


def upsert_defect(session: Session, defect: dict) -> Defect:
    azure_id = defect["azure_id"]
    row = session.scalar(select(Defect).where(Defect.azure_id == azure_id))
    if row is None:
        row = Defect(azure_id=azure_id)
        session.add(row)
    for field, value in defect.items():
        if field != "azure_id" and value is not None:
            setattr(row, field, value)
    return row


def get_defect(session: Session, defect_id: int) -> Defect | None:
    return session.get(Defect, defect_id)


def list_defects(session: Session, *, state: str | None = None,
                 severity: str | None = None, page: int = 1,
                 page_size: int = 50) -> tuple[Sequence[Defect], int]:
    stmt = select(Defect)
    if state:
        stmt = stmt.where(Defect.state == state)
    if severity:
        stmt = stmt.where(Defect.severity == severity)
    total = len(session.execute(stmt.with_only_columns(Defect.id)).all())
    items = session.scalars(
        stmt.order_by(Defect.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return items, total


def link_result_to_defect(session: Session, *, defect_id: int,
                          test_result_id: int | None, test_case_id: int | None,
                          reason: str) -> TestDefectLink:
    link = TestDefectLink(
        defect_id=defect_id, test_result_id=test_result_id,
        test_case_id=test_case_id, reason=reason, linked_by="manual",
        created_at=datetime.now(timezone.utc),
    )
    session.add(link)
    return link


def list_defect_links_for_defect(session: Session, defect_id: int) -> Sequence[TestDefectLink]:
    return session.scalars(
        select(TestDefectLink).where(TestDefectLink.defect_id == defect_id)
    ).all()


def history_window(session: Session, days: int = 90) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - timedelta(days=days), now
