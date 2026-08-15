"""Platform test configuration.

Sets environment BEFORE importing the app so pydantic-settings picks up a
Postgres-backed DATABASE_URL (override it to point at a dedicated test DB).
"""
from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql://uat:uat@127.0.0.1:5432/uat_test_intelligence_test",
    ),
)
os.environ.setdefault("API_TOKEN", "dev-token")
os.environ.setdefault("APP_ENV", "demo")
os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("REPORT_ENGINE", "manual")
# Tests own the notification flow (LogProvider only — no external calls).
os.environ["NOTIFICATIONS_ENABLED"] = "true"
os.environ.setdefault("LOG_FORMAT", "text")
os.environ.setdefault(
    "REPORTS_ROOT",
    str(Path(__file__).resolve().parent / "_artifacts" / "reports"),
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> Generator[None, None, None]:
    """Fresh schema for the whole session."""
    import app.models  # noqa: F401  (register all tables on Base.metadata)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:  # lifespan starts job worker + scheduler
        yield c


@pytest.fixture(scope="session")
def seeded(client: TestClient) -> dict:
    """Seed the demo dataset once per session (idempotent for our tests)."""
    from helpers import BASE, HDRS, wait_job

    r = client.post(f"{BASE}/demo/seed", headers=HDRS)
    assert r.status_code == 202, r.text
    wait_job(client, r.json()["job_id"], timeout=120)
    return {}
