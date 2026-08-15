"""Health endpoints."""
from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import db

router = APIRouter(tags=["health"])

_started = time.time()


@router.get("/health")
def health(session: Annotated[Session, Depends(db)]) -> dict:
    db_ok = "ok"
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok = f"error: {type(exc).__name__}"
    status = "ok" if db_ok == "ok" else "degraded"
    from app.core.types import __version__

    return {
        "status": status,
        "version": __version__,
        "database": db_ok,
        "uptime_seconds": round(time.time() - _started, 1),
        "time": time.time(),
    }
