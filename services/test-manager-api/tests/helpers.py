"""Shared helpers for platform tests."""
from __future__ import annotations

import time

BASE = "/api/v1"
HDRS = {"Authorization": "Bearer dev-token"}


def wait_job(client, job_id: str, timeout: float = 60) -> dict:
    """Poll a job until it reaches a terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get(f"{BASE}/jobs/{job_id}", headers=HDRS)
        assert r.status_code == 200, r.text
        job = r.json()
        if job["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return job
        time.sleep(0.25)
    raise TimeoutError(f"job {job_id} did not finish within {timeout}s")
