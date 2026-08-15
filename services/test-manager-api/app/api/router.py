"""Aggregate router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api import azure, coverage, defects, demo, health, misc, test_cases, test_manager, test_matrix, test_runs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(azure.router)
api_router.include_router(test_manager.router)
api_router.include_router(test_cases.router)
api_router.include_router(test_matrix.router)
api_router.include_router(test_runs.router)
api_router.include_router(coverage.router)
api_router.include_router(defects.router)
api_router.include_router(misc.reports_router)
api_router.include_router(misc.notifications_router)
api_router.include_router(misc.agents_router)
api_router.include_router(misc.jobs_router)
api_router.include_router(misc.dashboard_router)
api_router.include_router(misc.intelligence_router)
api_router.include_router(demo.router)
