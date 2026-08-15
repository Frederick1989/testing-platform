"""Azure schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ApiModel


class SyncRequest(BaseModel):
    organization: str = ""
    project: str = ""


class SyncResult(BaseModel):
    kind: str
    upserted: int
    status: str


class IterationOut(ApiModel):
    azure_id: str
    name: str
    path: str
    state: str
    start_date: datetime | None
    finish_date: datetime | None
    is_current: bool
    url: str


class WorkItemOut(ApiModel):
    azure_id: int
    type: str
    title: str
    description: str
    acceptance_criteria_raw: str
    state: str
    assigned_to: str
    iteration_name: str
    area_path: str
    created_at: datetime | None
    updated_at: datetime | None
    closed_at: datetime | None
    tags: list[str]
    url: str
    parent_azure_id: int | None
    last_synced_at: datetime


class WorkItemListParams(BaseModel):
    type: str | None = None
    state: str | None = None
    iteration: str | None = None
    page: int = 1
    page_size: int = 50


class PullRequestOut(ApiModel):
    azure_id: int
    title: str
    repo: str
    source_ref: str
    target_ref: str
    status: str
    author: str
    created_at: datetime | None
    updated_at: datetime | None
    url: str


class AzureLink(BaseModel):
    title: str
    href: str
    type: str
