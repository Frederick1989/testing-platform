"""Integration tests for the Azure sync pipeline (fake client, real DB)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from app.adapters.azure.client import AzureClientBase
from app.config import settings
from app.models.azure import WorkItem
from app.models.test import AcceptanceCriterion, Defect
from app.services import sync as sync_svc


class FakeAzureClient(AzureClientBase):
    def __init__(self, items: list[dict[str, Any]], *, iterations: list[dict[str, Any]] | None = None):
        self.items = items
        self.iterations = iterations or []

    async def query_work_items(self, wiql: str) -> list[dict[str, Any]]:
        return self.items

    async def get_work_item(self, work_item_id: int) -> dict[str, Any]:
        return next((i for i in self.items if int(i["id"]) == work_item_id), {})

    async def get_work_item_comments(self, work_item_id: int) -> list[dict[str, Any]]:
        return []

    async def list_iterations(self) -> list[dict[str, Any]]:
        return self.iterations

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


def test_closed_date_reads_process_specific_field(session, monkeypatch):
    monkeypatch.setattr(settings, "azure_closed_date_field", "Microsoft.VSTS.Common.ClosedDate")
    item = _item(5001, wtype="Issue", fields={
        "Microsoft.VSTS.Common.ClosedDate": "2026-01-05T00:00:00Z",
    })
    client = FakeAzureClient([item])

    _run(sync_svc.sync_work_items(session, client))
    session.commit()

    defect = session.query(Defect).filter(Defect.azure_id == 5001).one()
    assert defect.closed_at is not None


def test_derive_criteria_from_child_tasks(session, monkeypatch):
    monkeypatch.setattr(settings, "azure_story_type", "Epic")
    epic = _item(6001, wtype="Epic")
    task1 = _item(6002, wtype="Task", fields={
        "System.Parent": 6001, "System.Title": "Verify login flow",
    })
    task2 = _item(6003, wtype="Task", fields={
        "System.Parent": 6001, "System.Title": "Check error messages",
    })
    client = FakeAzureClient([epic, task1, task2])

    _run(sync_svc.sync_work_items(session, client))
    session.commit()

    epic_row = session.query(WorkItem).filter(WorkItem.azure_id == 6001).one()
    acs = session.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.work_item_id == epic_row.id
    ).all()
    assert {ac.text for ac in acs} == {"Verify login flow", "Check error messages"}


def test_missing_field_parsing():
    from app.adapters.azure.client import _missing_field

    assert (
        _missing_field("Azure DevOps API error 400: TF51535: Cannot find field System.ClosedDate.")
        == "System.ClosedDate"
    )
    assert _missing_field("some other error") is None


def test_work_item_fields_excludes_empty_ac_field(monkeypatch):
    from app.adapters.azure.client import AzureDevOpsClient

    monkeypatch.setattr(settings, "azure_acceptance_criteria_field", "  ")
    fields = AzureDevOpsClient._work_item_fields()
    assert "" not in fields
    assert "Microsoft.VSTS.Common.AcceptanceCriteria" not in fields


def test_basic_process_state_mapping():
    from app.services.sync import _map_state

    assert _map_state("To Do") == "New"
    assert _map_state("Doing") == "Active"
    assert _map_state("Done") == "Closed"
    assert _map_state("Resolved") == "Resolved"


def test_sync_iterations_marks_current_and_capitalizes_state(session):
    from app.models.azure import Iteration

    client = FakeAzureClient([], iterations=[{
        "id": "5d6c4e53-30e8-4e4b-b3cc-71b8e21da71f",
        "name": "Sprint 1",
        "path": "cyberpro\\Sprint 1",
        "attributes": {
            "timeFrame": "current",
            "startDate": "2026-08-01T00:00:00Z",
            "finishDate": "2026-08-14T00:00:00Z",
        },
    }])

    _run(sync_svc.sync_iterations(session, client))
    session.commit()

    it = session.query(Iteration).filter(Iteration.name == "Sprint 1").one()
    assert it.is_current is True
    assert it.state == "Current"
    assert it.start_date is not None
    assert it.finish_date is not None


def test_sync_iterations_prunes_stale_demo_sprints(session):
    from app.models.azure import Iteration
    from app.repositories import azure as az_repo

    az_repo.upsert_iteration(session, {
        "azure_id": "stale-1", "name": "Sprint 01", "path": "cyberpro\\Sprint 01",
        "state": "Closed", "start_date": None, "finish_date": None,
        "is_current": False, "url": "", "last_synced_at": datetime.now(timezone.utc),
    })
    session.flush()
    stale_row = session.query(Iteration).filter(Iteration.azure_id == "stale-1").one()
    model = sync_svc._work_item_to_model(
        FakeAzureClient([]), _item(7001, wtype="Epic"), now=datetime.now(timezone.utc)
    )
    work = az_repo.upsert_work_item(session, model)
    work.iteration_id = stale_row.id
    session.commit()

    client = FakeAzureClient([], iterations=[{
        "id": "5d6c4e53-30e8-4e4b-b3cc-71b8e21da71f",
        "name": "Sprint 1", "path": "cyberpro\\Sprint 1",
        "attributes": {"timeFrame": "current"},
    }])
    _run(sync_svc.sync_iterations(session, client))
    session.commit()

    assert session.query(Iteration).filter(Iteration.azure_id == "stale-1").first() is None
    work_row = session.query(WorkItem).filter(WorkItem.azure_id == 7001).one()
    assert work_row.iteration_id is None
