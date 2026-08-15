"""Shared API dependencies."""
from __future__ import annotations

from app.db import get_session

db = get_session
