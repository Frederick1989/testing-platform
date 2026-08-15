"""API-level tests: auth, seeded state, metrics endpoints, reports, jobs."""
from __future__ import annotations

import pytest

from helpers import BASE, HDRS, wait_job


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_auth_required(client):
    assert client.get(f"{BASE}/dashboard/summary").status_code == 401
    assert client.get(f"{BASE}/coverage/summary").status_code == 401
    assert client.post(f"{BASE}/demo/seed").status_code == 401


def test_unknown_token_rejected(client):
    r = client.get(f"{BASE}/dashboard/summary", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


@pytest.fixture
def demo_seeded(client):
    r = client.post(f"{BASE}/demo/seed", headers=HDRS)
    assert r.status_code == 202
    wait_job(client, r.json()["job_id"], timeout=90)


def test_dashboard_summary(client, demo_seeded):
    r = client.get(f"{BASE}/dashboard/summary", headers=HDRS)
    assert r.status_code == 200
    body = r.json()
    assert "coverage" in body
    assert "defects" in body
    assert "current_sprint" in body
    assert body["recent_runs"], "seeded demo should produce test runs"


def test_coverage_endpoints(client, demo_seeded):
    summary = client.get(f"{BASE}/coverage/summary", headers=HDRS).json()
    assert summary["requirement"] > 0
    by_story = client.get(f"{BASE}/coverage/by-story", headers=HDRS).json()
    assert by_story["items"]
    gaps = client.get(f"{BASE}/coverage/gaps", headers=HDRS).json()
    assert "uncovered_acceptance_criteria" in gaps


def test_matrix_roundtrip(client, demo_seeded):
    r = client.get(f"{BASE}/test-matrix", headers=HDRS)
    assert r.status_code == 200
    items = r.json()["items"]
    assert items, "seeded stories should appear in the matrix"
    story_ref = items[0]["work_item_id"]
    detail = client.get(f"{BASE}/test-matrix/{story_ref}", headers=HDRS)
    assert detail.status_code == 200


def test_defects_summary_and_list(client, demo_seeded):
    summary = client.get(f"{BASE}/defects/summary", headers=HDRS).json()
    assert summary["total"] > 0
    listing = client.get(f"{BASE}/defects", headers=HDRS).json()
    assert listing["items"]


def test_velocity_flaky_regression_risks(client, demo_seeded):
    assert client.get(f"{BASE}/velocity", headers=HDRS).status_code == 200
    flaky = client.get(f"{BASE}/flaky-tests", headers=HDRS).json()
    assert "tests" in flaky
    reg = client.get(f"{BASE}/regression", headers=HDRS).json()
    assert set(reg) >= {"new_failures", "recovered", "repeated_failures"}
    assert client.get(f"{BASE}/risks", headers=HDRS).status_code == 200


def test_sprints_and_ready_stories(client, demo_seeded):
    sprints = client.get(f"{BASE}/sprints", headers=HDRS).json()
    assert sprints["items"]
    ready = client.get(f"{BASE}/test-manager/stories/ready", headers=HDRS)
    assert ready.status_code == 200


def test_agents_and_jobs(client, demo_seeded):
    agents = client.get(f"{BASE}/agents", headers=HDRS).json()
    assert agents["items"]
    r = client.post(f"{BASE}/agents/{agents['items'][0]['name']}/run", headers=HDRS)
    assert r.status_code in (200, 202)
    jobs = client.get(f"{BASE}/jobs", headers=HDRS).json()
    assert jobs["items"]


def test_report_generation_roundtrip(client, demo_seeded):
    r = client.post(f"{BASE}/reports/generate", headers=HDRS, json={})
    assert r.status_code == 202
    wait_job(client, r.json()["job_id"], timeout=90)

    latest = client.get(f"{BASE}/reports/latest", headers=HDRS).json()
    assert latest["status"] == "GENERATED"
    archive = client.get(f"{BASE}/reports/archive", headers=HDRS).json()
    assert archive["items"]
    aid = archive["items"][0]["id"]

    html = client.get(f"{BASE}/reports/archive/{aid}/html")
    assert html.status_code == 200
    assert b"<html" in html.content.lower()
    pdf = client.get(f"{BASE}/reports/archive/{aid}/pdf")
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF" or b"<html" in pdf.content.lower()


def test_notification_flow(client, demo_seeded):
    r = client.post(f"{BASE}/notifications/test", headers=HDRS)
    assert r.status_code == 200
    assert r.json()["status"] == "SENT"
    items = client.get(f"{BASE}/notifications", headers=HDRS).json()["items"]
    assert any(n["status"] == "SENT" for n in items)
