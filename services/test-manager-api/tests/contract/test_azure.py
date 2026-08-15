"""Contract tests for the Azure DevOps adapter.

Verifies error sanitisation and that the PAT never leaks.
"""
from __future__ import annotations

import asyncio

import pytest
from httpx import Response

from app.adapters.azure.client import (
    AzureDevOpsClient,
    NullAuthProvider,
    PatAuthProvider,
    _safe_azure_error,
    strip_html,
)
from app.core.errors import DependencyUnavailableError


def test_pat_is_base64_basic_auth():
    provider = PatAuthProvider("super-secret-pat-value")
    headers = asyncio.run(provider.auth_headers())
    assert headers["Authorization"].startswith("Basic ")
    assert "super-secret-pat-value" not in headers["Authorization"]


def test_client_raises_when_unconfigured():
    client = AzureDevOpsClient(org="", project="", auth=NullAuthProvider())
    assert client.configured is False
    with pytest.raises(DependencyUnavailableError):
        asyncio.run(client.query_work_items("SELECT * FROM WorkItems"))


def test_strip_html():
    assert strip_html("<p>hello <b>world</b></p>") == "hello world"
    assert strip_html(None) == ""
    assert strip_html("  a   b  ") == "a b"


def test_azure_error_redacts_pat_query_param():
    resp = Response(400, json={"message": "failed with token=abc123 and pat=sekrit123"})
    out = _safe_azure_error(resp)
    assert "sekrit123" not in out
    assert "REDACTED" in out
