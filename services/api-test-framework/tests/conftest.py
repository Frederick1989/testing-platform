"""Shared fixtures for the weather mock API test suite."""
from __future__ import annotations

import os

import pytest
import requests


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("WEATHER_URL", "http://localhost:5000")


@pytest.fixture(scope="session")
def client() -> requests.Session:
    return requests.Session()


@pytest.fixture
def current_url(base_url: str) -> str:
    return f"{base_url}/api/weather/current"


@pytest.fixture
def forecast_url(base_url: str) -> str:
    return f"{base_url}/api/weather/forecast"


@pytest.fixture
def timeout_seconds() -> float:
    return float(os.environ.get("WEATHER_TIMEOUT", "5"))
