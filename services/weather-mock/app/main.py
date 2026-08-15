"""Weather mock API — the system under test for the demo (port 5000).

Deterministic, seeded responses. Deliberately includes defects so the UAT
platform has real failures to surface (matching the seeded demo defects):

  - empty city name            -> HTTP 500
  - city names with accents    -> HTTP 404
  - unicode/non-ascii fallback -> HTTP 400
  - unknown city               -> HTTP 404
  - some forecasts are slow    -> configurable delay (simulated timeout)
"""
from __future__ import annotations

import hashlib
import random
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .config import settings

app = FastAPI(
    title="Weather Mock API (under test)",
    description="Deterministic weather API used as the demo system under test.",
    version="1.0.0",
)

_KNOWN_CITIES = {
    "london": (51.5074, -0.1278),
    "paris": (48.8566, 2.3522),
    "berlin": (52.5200, 13.4050),
    "madrid": (40.4168, -3.7038),
    "rome": (41.9028, 12.4964),
    "amsterdam": (52.3676, 4.9041),
    "lisbon": (38.7223, -9.1393),
    "vienna": (48.2082, 16.3738),
    "oslo": (59.9139, 10.7522),
    "helsinki": (60.1699, 24.9384),
    "dublin": (53.3498, -6.2603),
    "zurich": (47.3769, 8.5417),
    "stockholm": (59.3293, 18.0686),
    "brussels": (50.8503, 4.3517),
    "reykjavik": (64.1466, -21.9426),
    "athens": (37.9838, 23.7275),
    "warsaw": (52.2297, 21.0122),
    "prague": (50.0755, 14.4378),
    "budapest": (47.4979, 19.0402),
    "copenhagen": (55.6761, 12.5683),
}


def _seed_for(city: str) -> int:
    return int(hashlib.sha256(city.lower().encode()).hexdigest()[:8], 16)


def _conditions(seed: int) -> str:
    rng = random.Random(seed)
    return rng.choice(
        ["Clear", "Partly cloudy", "Cloudy", "Rain", "Snow", "Thunderstorm", "Fog", "Windy"]
    )


def _normalize_city(city: str) -> str | None:
    if city != city.strip():
        return None
    return city.strip().lower()


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "timestamp": datetime.now(timezone.utc).isoformat()},
    )


@app.get("/api/weather/health")
def health():
    return {"status": "ok", "service": "weather-mock", "version": "1.0.0"}


@app.get("/api/weather/current/{city:path}")
def current_weather(city: str):
    if not city:
        # Defect: empty city name returns 500
        raise HTTPException(status_code=500, detail="internal error: empty city name")
    if any(ord(ch) > 127 for ch in city):
        # Defect: accents / non-ascii -> 404
        raise HTTPException(status_code=404, detail="city not found")
    norm = _normalize_city(city)
    if norm is None:
        raise HTTPException(status_code=400, detail="invalid city name")
    if norm not in _KNOWN_CITIES:
        raise HTTPException(status_code=404, detail="city not found")
    lat, lon = _KNOWN_CITIES[norm]
    seed = _seed_for(norm)
    rng = random.Random(seed)
    temp = round(rng.uniform(-8.0, 34.0), 1)
    return {
        "city": norm,
        "country": "demo",
        "lat": lat,
        "lon": lon,
        "temperature_c": temp,
        "feels_like_c": round(temp + rng.uniform(-3, 3), 1),
        "condition": _conditions(seed),
        "humidity": rng.randint(20, 100),
        "wind_kph": round(rng.uniform(0, 40), 1),
        "pressure_hpa": rng.randint(980, 1035),
        "visibility_km": rng.randint(1, 40),
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/weather/forecast/{city:path}")
def forecast(city: str, days: int = Query(5, ge=1, le=10)):
    if not city:
        raise HTTPException(status_code=500, detail="internal error: empty city name")
    if any(ord(ch) > 127 for ch in city):
        raise HTTPException(status_code=404, detail="city not found")
    norm = _normalize_city(city)
    if norm is None:
        raise HTTPException(status_code=400, detail="invalid city name")
    if norm not in _KNOWN_CITIES:
        raise HTTPException(status_code=404, detail="city not found")

    if settings.forecast_timeout_city and norm == settings.forecast_timeout_city.lower():
        # Defect: forecast endpoint times out for this city
        time.sleep(settings.forecast_timeout_seconds)

    seed = _seed_for(norm)
    rng = random.Random(seed)
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    daily = []
    for i in range(days):
        day_seed = seed + i
        drng = random.Random(day_seed)
        daily.append(
            {
                "date": (start + timedelta(days=i)).date().isoformat(),
                "temp_min_c": round(drng.uniform(-12, 18), 1),
                "temp_max_c": round(drng.uniform(2, 38), 1),
                "condition": _conditions(day_seed),
                "precip_mm": round(drng.uniform(0, 25), 1),
            }
        )
    return {
        "city": norm,
        "days": daily,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/")
def index():
    return {
        "service": "weather-mock",
        "docs": "/docs",
        "health": "/api/weather/health",
        "current": "/api/weather/current/{city}",
        "forecast": "/api/weather/forecast/{city}?days=5",
        "known_cities": sorted(_KNOWN_CITIES),
        "defects_enabled": {
            "empty_city_500": True,
            "accented_city_404": True,
            "forecast_timeout_city": settings.forecast_timeout_city or None,
        },
    }
