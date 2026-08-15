"""Tests for the forecast endpoint."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize("city", ["London", "Berlin", "Rome"])
def test_forecast_default_five_days(city: str, forecast_url: str, client) -> None:
    resp = client.get(f"{forecast_url}/{city}", timeout=15)
    assert resp.status_code == 200, resp.text
    days = resp.json()["days"]
    assert len(days) == 5
    for day in days:
        for field in ("date", "temp_min_c", "temp_max_c", "condition", "precip_mm"):
            assert field in day, f"missing field: {field}"


def test_forecast_days_param(forecast_url: str, client) -> None:
    resp = client.get(f"{forecast_url}/London?days=3", timeout=15)
    assert resp.status_code == 200
    assert len(resp.json()["days"]) == 3


def test_forecast_days_bounds(forecast_url: str, client) -> None:
    resp = client.get(f"{forecast_url}/London?days=11", timeout=15)
    assert resp.status_code in (400, 422)


def test_forecast_unknown_city_returns_appropriate_error(forecast_url: str, client) -> None:
    resp = client.get(f"{forecast_url}/nowhereville", timeout=15)
    assert resp.status_code == 404, resp.text
    assert "error" in resp.json()


def test_forecast_accented_city(forecast_url: str, client) -> None:
    # KNOWN DEFECT: valid accented city rejected with 404.
    resp = client.get(f"{forecast_url}/Lisboa", timeout=15)
    assert resp.status_code == 200, resp.text
