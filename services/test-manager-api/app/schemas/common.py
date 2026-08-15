"""Common response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    detail: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Page(ApiModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    uptime_seconds: float
    time: datetime
