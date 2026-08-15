"""Azure DevOps REST API client behind an interface.

Authentication is injected so it can later be changed (e.g. OAuth, managed
identity) without touching callers.
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from app.config import settings
from app.core.errors import BadRequestError, DependencyUnavailableError

logger = logging.getLogger("app.azure")

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class AzureAuthProvider(Protocol):
    async def auth_headers(self) -> dict[str, str]:
        ...


class PatAuthProvider:
    """Basic-auth PAT authentication. The PAT is never logged."""

    def __init__(self, pat: str):
        self._pat = pat

    async def auth_headers(self) -> dict[str, str]:
        import base64

        encoded = base64.b64encode(f":{self._pat}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}


class NullAuthProvider:
    async def auth_headers(self) -> dict[str, str]:
        return {}


class AzureClientBase(ABC):
    @abstractmethod
    async def query_work_items(self, wiql: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_work_item(self, work_item_id: int) -> dict[str, Any]:
        ...

    @abstractmethod
    async def get_work_item_comments(self, work_item_id: int) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def list_iterations(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def list_pull_requests(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def add_work_item_comment(self, work_item_id: int, text: str) -> None:
        ...

    @abstractmethod
    async def create_pull_request(self, *, title: str, source_ref: str,
                                  target_ref: str, description: str) -> dict[str, Any]:
        ...


def strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = _HTML_TAG_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


class AzureDevOpsClient(AzureClientBase):
    """HTTP client for Azure DevOps REST APIs."""

    def __init__(
        self,
        *,
        org: str,
        project: str,
        auth: AzureAuthProvider,
        api_version: str | None = None,
        timeout: float = 30.0,
    ):
        self._org = org
        self._project = project
        self._auth = auth
        self._api_version = api_version or settings.azure_devops_api_version
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._org and self._project)

    def _url(self, path: str, *, project: bool = True) -> str:
        base = f"https://dev.azure.com/{self._org}"
        if project:
            base += f"/{self._project}"
        return f"{base}/_apis/{path}"

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if not self.configured:
            raise DependencyUnavailableError(
                "Azure DevOps is not configured (set AZURE_DEVOPS_ORG/PROJECT)"
            )
        headers = kwargs.pop("headers", {})
        headers.update(await self._auth.auth_headers())
        params = dict(kwargs.pop("params", {}))
        params.setdefault("api-version", self._api_version)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(method, url, headers=headers, params=params, **kwargs)
        except httpx.HTTPError as exc:
            raise DependencyUnavailableError(f"Azure DevOps unreachable: {exc}") from exc
        if resp.status_code >= 400:
            detail = _safe_azure_error(resp)
            raise BadRequestError(f"Azure DevOps API error {resp.status_code}: {detail}")
        return resp

    async def query_work_items(self, wiql: str) -> list[dict[str, Any]]:
        url = self._url("wit/wiql", project=True)
        resp = await self._request(
            "POST", url, json={"query": wiql}
        )
        data = resp.json()
        items = [w for w in data.get("workItems", [])]
        return await self._expand_work_items([int(w["id"]) for w in items])

    async def _expand_work_items(self, ids: list[int]) -> list[dict[str, Any]]:
        if not ids:
            return []
        url = self._url("wit/workitemsbatch")
        payload = {"ids": ids[:199], "fields": [
            "System.Id", "System.WorkItemType", "System.Title", "System.Description",
            "Microsoft.VSTS.Common.AcceptanceCriteria", "Microsoft.VSTS.Common.Severity",
            "Microsoft.VSTS.Common.ResolvedDate",
            "System.State",
            "System.AssignedTo", "System.IterationPath", "System.AreaPath",
            "System.CreatedDate", "System.ChangedDate", "System.ClosedDate",
            "System.Tags", "System.Parent", "System.CommentCount", "System.Url",
        ]}
        resp = await self._request("POST", url, json=payload)
        return resp.json().get("value", [])

    async def get_work_item(self, work_item_id: int) -> dict[str, Any]:
        url = self._url(f"wit/workitems/{work_item_id}")
        resp = await self._request("GET", url)
        return resp.json()

    async def get_work_item_comments(self, work_item_id: int) -> list[dict[str, Any]]:
        url = self._url(f"wit/workItems/{work_item_id}/comments")
        try:
            resp = await self._request("GET", url)
            return resp.json().get("comments", [])
        except BadRequestError:
            return []

    async def list_iterations(self) -> list[dict[str, Any]]:
        url = self._url("work/teamsettings/iterations", project=True)
        resp = await self._request("GET", url)
        return resp.json().get("value", [])

    async def list_pull_requests(self) -> list[dict[str, Any]]:
        url = self._url("git/pullrequests")
        resp = await self._request("GET", url, params={"searchCriteria.status": "all"})
        return resp.json().get("value", [])

    async def add_work_item_comment(self, work_item_id: int, text: str) -> None:
        url = self._url(f"wit/workitems/{work_item_id}/comments")
        await self._request("POST", url, json={"text": text})

    async def create_pull_request(
        self, *, title: str, source_ref: str, target_ref: str, description: str
    ) -> dict[str, Any]:
        if not settings.azure_git_repo_name:
            raise BadRequestError("AZURE_GIT_REPO_NAME is required to create a PR")
        repo = settings.azure_git_repo_name
        url = self._url(f"git/repositories/{repo}/pullrequests", project=True)
        body = {
            "title": title,
            "description": description,
            "sourceRefName": f"refs/heads/{source_ref}",
            "targetRefName": f"refs/heads/{target_ref}",
            "isDraft": False,
        }
        resp = await self._request("POST", url, json=body)
        return resp.json()


def _safe_azure_error(resp: httpx.Response) -> str:
    """Extract an Azure error message without ever echoing the PAT."""
    try:
        msg = resp.json().get("message", resp.text[:500])
    except Exception:  # noqa: BLE001
        msg = resp.text[:500]
    # defensive redaction in case Azure echoes query params
    msg = re.sub(r"(pat|authorization|token)=[^&\s]+", r"\1=REDACTED", msg, flags=re.I)
    return msg[:1000]


def _extract_field(fields: Mapping[str, Any], name: str, default: Any = "") -> Any:
    return fields.get(name, default)


def make_client() -> AzureDevOpsClient:
    auth: AzureAuthProvider = (
        PatAuthProvider(settings.azure_devops_pat)
        if settings.azure_devops_pat
        else NullAuthProvider()
    )
    return AzureDevOpsClient(
        org=settings.azure_devops_org,
        project=settings.azure_devops_project,
        auth=auth,
    )
