"""ID generation utilities."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"


def run_id() -> str:
    return new_id("run")


def job_id() -> str:
    return new_id("job")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
