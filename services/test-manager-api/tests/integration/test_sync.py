"""Integration tests for the Azure sync pipeline (fake client, real DB)."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.adapters.azure.client import AzureClientBase
from app.config import settings
from app.models.azure import WorkItem
from app.models.test import AcceptanceCriterion, Defect
from app.services import sync as sync_svc


class FakeAzureClient(AzureClientBase):
    def __init__(self, items: list[dict[str, Any]]):
        self.items = items

    async def query_work_items(self, wiql: str) -> list[dict[str, Any]]:
        return self.items

    async def get_work_item(self, work_item_id: int) -> dict[str, Any]:
        return next((i for i in self.items if int(i["id"]) == work_item_id), {})

    async def get_work_item_comments(self, work_item_id: int) -> list[dict[str, Any]]:
        return []

    async def list_iterations(self) -> list[dict[str, Any]]:
        return []

    async def list_pull_requests(self) -> list[dict[str, Any]]:
        return []

    async def add_work_item_comment(self, work_item_id: int, text: str) -> None:
        return None

    async def create_pull_request(self, *, title: str, source_ref: str,
                                  target_ref: str, description: str) -> dict[str, Any]:
        return {}


def _item(work_item_id: int, *, wtype: str, fields: dict[str, Any] | None = None) -> dict:
    base: dict[str, Any] = {
        "System.Id": work_item_id,
        "System.WorkItemType": wtype,
        "System.Title": f"Item {work_item_id}",
        "System.State": "New",
        "System.CreatedDate": "2026-01-01T00:00:00Z",
        "System.ChangedDate": "2026-01-02T00:00:00Z",
    }
    if fields:
        base.update(fields)
    return {"id": work_item_id, "fields": base}


def _run(coro) -> Any:
    return asyncio.run(coro)


@pytest.fixture(scope="session")
def session():
    from app.db import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def test_sync_ingests_story_and_defects(session):
    story = _item(1001, wtype="User Story", fields={
        "Microsoft.VSTS.Common.AcceptanceCriteria": "1. Criterion one\n2. Criterion two",
        "System.IterationPath": "Project\\Sprint 1",
        "System.State": "Active",
    })
    issue = _item(2001, wtype="Issue", fields={
        "Microsoft.VSTS.Common.Severity": "2 - High",
        "System.State": "Active",
        "System.Parent": 1001,
        "System.IterationPath": "Project\\Sprint 1",
    })
    bug = _item(2002, wtype="Bug", fields={
        "Microsoft.VSTS.Common.Severity": "Critical",
        "System.State": "Closed",
        "System.Parent": 1001,
        "System.ClosedDate": "2026-01-05T00:00:00Z",
    })
    client = FakeAzureClient([story, issue, bug])

    count = _run(sync_svc.sync_work_items(session, client))
    session.commit()

    assert count == 3
    work_items = session.query(WorkItem).filter(WorkItem.azure_id.in_([1001, 2001, 2002])).all()
    assert len(work_items) == 3

    acs = session.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.work_item_id.in_([w.id for w in work_items])
    ).all()
    assert {ac.text for ac in acs} == {"Criterion one", "Criterion two"}

    defects = {d.azure_id: d for d in session.query(Defect).filter(
        Defect.azure_id.in_([2001, 2002])
    ).all()}
    assert len(defects) == 2
    assert defects[2001].severity == "HIGH"
    assert defects[2001].state == "Active"
    assert defects[2001].story_work_item_id == 1001
    assert defects[2001].iteration_name == "Sprint 1"
    assert defects[2002].severity == "CRITICAL"
    assert defects[2002].state == "Closed"
    assert defects[2002].closed_at is not None


def test_sync_uses_configured_acceptance_criteria_field(session, monkeypatch):
    monkeypatch.setattr(settings, "azure_acceptance_criteria_field", "Custom.AC")
    item = _item(3001, wtype="Epic", fields={"Custom.AC": "Custom criterion"})
    client = FakeAzureClient([item])

    _run(sync_svc.sync_work_items(session, client))
    session.commit()

    row = session.query(WorkItem).filter(WorkItem.azure_id == 3001).one()
    acs = session.query(AcceptanceCriterion).filter(AcceptanceCriterion.work_item_id == row.id).all()
    assert [ac.text for ac in acs] == ["Custom criterion"]


def test_story_type_is_configurable(session, monkeypatch):
    from app.services import coverage as coverage_svc

    monkeypatch.setattr(settings, "azure_story_type", "Epic")
    epic = _item(4001, wtype="Epic")
    story = _item(4002, wtype="User Story")
    client = FakeAzureClient([epic, story])

    _run(sync_svc.sync_work_items(session, client))
    session.commit()

    stories = coverage_svc._stories(session)
    azure_ids = {s.azure_id for s in stories}
    assert 4001 in azure_ids
    assert 4002 not in azure_ids
