"""Data access for Azure-synced entities."""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import WorkItemType
from app.models.azure import AzureComment, Iteration, PullRequest, WorkItem
from app.models.test import AcceptanceCriterion


def upsert_iteration(session: Session, iteration: dict) -> Iteration:
    azure_id = iteration["azure_id"]
    row = session.scalar(select(Iteration).where(Iteration.azure_id == azure_id))
    if row is None:
        row = Iteration(azure_id=azure_id)
        session.add(row)
    for field, value in iteration.items():
        if field != "azure_id" and value is not None:
            setattr(row, field, value)
    return row


def upsert_work_item(session: Session, work_item: dict) -> WorkItem:
    azure_id = work_item["azure_id"]
    row = session.scalar(select(WorkItem).where(WorkItem.azure_id == azure_id))
    if row is None:
        row = WorkItem(azure_id=azure_id)
        session.add(row)
    for field, value in work_item.items():
        if field != "azure_id" and value is not None:
            setattr(row, field, value)
    return row


def get_work_item(session: Session, work_item_id: int) -> WorkItem | None:
    return session.get(WorkItem, work_item_id)


def get_work_item_by_azure_id(session: Session, azure_id: int) -> WorkItem | None:
    return session.scalar(select(WorkItem).where(WorkItem.azure_id == azure_id))


def resolve_work_item(session: Session, ref: int) -> WorkItem | None:
    """Resolve a story reference that may be a PK or an Azure DevOps id."""
    row = session.get(WorkItem, ref)
    if row is not None:
        return row
    return get_work_item_by_azure_id(session, ref)


def list_work_items(
    session: Session,
    *,
    type: str | None = None,
    state: str | None = None,
    iteration: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[Sequence[WorkItem], int]:
    filters = [WorkItem.is_active.is_(True)]
    if type:
        filters.append(WorkItem.type == type)
    if state:
        filters.append(WorkItem.state == state)
    if iteration:
        filters.append(WorkItem.iteration_name == iteration)
    stmt = select(WorkItem).where(*filters)
    total = len(session.execute(stmt.with_only_columns(WorkItem.id)).all())
    items = session.scalars(
        stmt.order_by(WorkItem.azure_id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return items, total


def upsert_pull_request(session: Session, pr: dict) -> PullRequest:
    azure_id = pr["azure_id"]
    row = session.scalar(select(PullRequest).where(PullRequest.azure_id == azure_id))
    if row is None:
        row = PullRequest(azure_id=azure_id)
        session.add(row)
    for field, value in pr.items():
        if field != "azure_id" and value is not None:
            setattr(row, field, value)
    return row


def list_pull_requests(session: Session, limit: int = 50) -> Sequence[PullRequest]:
    return session.scalars(
        select(PullRequest).order_by(PullRequest.created_at.desc()).limit(limit)
    ).all()


def upsert_acceptance_criteria(
    session: Session, work_item_id: int, texts: list[str]
) -> list[AcceptanceCriterion]:
    existing = list(
        session.scalars(
            select(AcceptanceCriterion)
            .where(AcceptanceCriterion.work_item_id == work_item_id)
            .order_by(AcceptanceCriterion.sort_order)
        )
    )
    existing = [ac for ac in existing if ac.is_active]
    existing.sort(key=lambda ac: ac.sort_order)
    rows: list[AcceptanceCriterion] = []
    for idx, text in enumerate(texts):
        if idx < len(existing):
            ac = existing[idx]
            ac.text = text
            ac.sort_order = idx
            rows.append(ac)
        else:
            ac = AcceptanceCriterion(
                work_item_id=work_item_id,
                text=text,
                sort_order=idx,
                status="NOT_COVERED",
            )
            session.add(ac)
            rows.append(ac)
    for extra in existing[len(texts):]:
        extra.is_active = False
    return rows


def count_acceptance_criteria(session: Session, work_item_id: int) -> int:
    return session.scalar(
        select(func.count(AcceptanceCriterion.id)).where(
            AcceptanceCriterion.work_item_id == work_item_id,
            AcceptanceCriterion.is_active.is_(True),
        )
    ) or 0


def upsert_comment(session: Session, comment: dict) -> AzureComment:
    azure_comment_id = comment["azure_comment_id"]
    row = session.scalar(
        select(AzureComment).where(AzureComment.azure_comment_id == azure_comment_id)
    )
    if row is None:
        row = AzureComment(azure_comment_id=azure_comment_id)
        session.add(row)
    for field, value in comment.items():
        if field != "azure_comment_id" and value is not None:
            setattr(row, field, value)
    return row


def list_iterations(session: Session) -> Sequence[Iteration]:
    return session.scalars(select(Iteration).order_by(Iteration.start_date)).all()


def get_iteration_by_name(session: Session, name: str) -> Iteration | None:
    return session.scalar(select(Iteration).where(Iteration.name == name))


def get_current_iteration(session: Session) -> Iteration | None:
    return session.scalar(
        select(Iteration)
        .where(Iteration.is_current.is_(True))
        .order_by(Iteration.start_date.desc())
    )


def count_work_items_by_type(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(WorkItem.type, WorkItem.id.count()).group_by(WorkItem.type)
    ).all()
    return {t: c for t, c in rows}


def types_for_query(*, stories_only: bool = False) -> list[str]:
    from app.config import settings

    if stories_only:
        return [settings.azure_story_type]
    types = {
        WorkItemType.EPIC.value,
        WorkItemType.FEATURE.value,
        WorkItemType.TASK.value,
        settings.azure_story_type,
    }
    types.update(t for t in settings.azure_defect_types.split(",") if t.strip())
    return sorted(types)
