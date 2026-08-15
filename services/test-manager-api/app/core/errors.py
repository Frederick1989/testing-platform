"""Application errors and problem-detail responses."""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class DemoOnlyError(ForbiddenError):
    code = "demo_only"


class DependencyUnavailableError(AppError):
    status_code = 501
    code = "dependency_unavailable"


def problem_response(exc: AppError, request_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "request_id": request_id,
            "detail": exc.detail,
        }
    }
