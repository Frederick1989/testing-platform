"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings
from app.core.errors import AppError, problem_response
from app.core.logging import request_id_var, setup_logging
from app.core.types import __version__

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):

    setup_logging()
    logger.info("starting %s v%s env=%s", settings.app_name, __version__, settings.app_env)
    if not settings.api_token:
        logger.warning(
            "API_TOKEN is not set — API is running WITHOUT authentication. "
            "Set API_TOKEN in production."
        )
    from app.adapters.azure.client import make_client

    client = make_client()
    if not client.configured:
        logger.warning(
            "Azure DevOps not configured (AZURE_DEVOPS_ORG/PROJECT unset). "
            "Use /demo/seed in demo mode for sample data."
        )

    from app.jobs.agents import build_registry
    from app.jobs.manager import JobManager

    job_manager = JobManager(build_registry())
    app.state.job_manager = job_manager
    worker_task = None
    scheduler = None
    if settings.agents_enabled:
        import asyncio

        worker_task = asyncio.create_task(job_manager.run_worker())
        from app.jobs.scheduler import start_scheduler

        scheduler = start_scheduler()
        app.state.scheduler = scheduler

    from app.services.notifications import register_handlers

    register_handlers()

    yield

    if scheduler:
        scheduler.shutdown(wait=False)
    if worker_task:
        worker_task.cancel()
    await job_manager.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        import time as time_mod
        from uuid import uuid4

        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = request_id_var.set(request_id)
        start = time_mod.perf_counter()
        response = await call_next(request)
        duration_ms = int((time_mod.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%s",
            request.method, request.url.path, response.status_code, duration_ms,
        )
        request_id_var.reset(token)
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID") or "-"
        logger.warning(
            "app_error code=%s path=%s message=%s",
            exc.code, request.url.path, exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=problem_response(exc, request_id),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID") or "-"
        logger.exception(
            "unhandled error path=%s", request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "internal server error",
                    "request_id": request_id,
                }
            },
        )

    app.include_router(api_router)

    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()
