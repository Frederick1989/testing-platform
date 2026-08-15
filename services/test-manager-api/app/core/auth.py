"""Bearer-token auth dependency for the API."""
from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header

from app.config import settings
from app.core.errors import AuthError


async def require_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not settings.api_token:
        return "anonymous"
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, settings.api_token):
        raise AuthError("Invalid API token")
    return token


def require_demo() -> None:
    if not settings.is_demo:
        from app.core.errors import DemoOnlyError

        raise DemoOnlyError("Endpoint is only available in demo/development mode")


AuthDep = Depends(require_token)
DemoDep = Depends(require_demo)
