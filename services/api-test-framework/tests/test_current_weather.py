"""Tests for the current weather endpoint."""
from __future__ import annotations

import pytest


def test_health(base_url: str, client) -> None:
    resp = client.get(f"{base_url}/api/weather/health", timeout=10)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.parametrize("city", ["London", "london", "PARIS", "Berlin", "Oslo"])
def test_current_weather_returns_required_fields(city: str, current_url: str, client) -> None:
    resp = client.get(f"{current_url}/{city}", timeout=10)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for field in ("city", "temperature_c", "feels_like_c", "condition",
                  "humidity", "wind_kph", "observed_at"):
        assert field in body, f"missing field: {field}"
    assert isinstance(body["temperature_c"], (int, float))


@pytest.mark.parametrize("city", ["atlantis", "unknownville", "xyz123"])
def test_unknown_city_returns_appropriate_error(city: str, current_url: str, client) -> None:
    resp = client.get(f"{current_url}/{city}", timeout=10)
    assert resp.status_code == 404, resp.text
    assert "error" in resp.json()


def test_empty_city_returns_client_error(current_url: str, client) -> None:
    # Acceptance criterion: invalid input yields an appropriate (client) error.
    # KNOWN DEFECT: the API returns 500; this test documents the bug and fails.
    resp = client.get(f"{current_url}/", timeout=10)
    assert resp.status_code in (400, 404, 422), resp.text


def test_accented_city_returns_appropriate_error(current_url: str, client) -> None:
    # KNOWN DEFECT: accents return 404 though the city is valid; documents the bug.
    resp = client.get(f"{current_url}/M%C3%BCnchen", timeout=10)
    assert resp.status_code == 200, resp.text


def test_city_name_with_leading_space_rejected(current_url: str, client) -> None:
    resp = client.get(f"{current_url}/%20London", timeout=10)
    assert resp.status_code in (400, 404, 422), resp.text
