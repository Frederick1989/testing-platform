"""Configuration for the weather mock API."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    forecast_timeout_city: str = ""
    forecast_timeout_seconds: float = 12.0

    class Config:
        env_prefix = "WEATHER_"
        env_file = ".env"


settings = Settings()
