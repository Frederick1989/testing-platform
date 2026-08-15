"""Configuration for the API test framework."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    weather_url: str = "http://localhost:5000"
    weather_timeout: float = 5.0
    runs_dir: str = str(Path(__file__).resolve().parent.parent / "reports")
    tests_dir: str = str(Path(__file__).resolve().parent.parent / "tests")
    python_bin: str = os.environ.get("PYTHON_BIN", "python3")
    run_timeout: int = 300
    max_runs: int = 50
    pytest_html_installed: bool = True

    class Config:
        env_prefix = "API_TESTS_"
        env_file = ".env"

    def env_overrides(self) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if k.startswith("WEATHER_")}


settings = Settings()
