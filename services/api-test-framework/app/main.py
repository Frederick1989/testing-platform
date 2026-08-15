"""API test framework — runs the pytest suite against the weather mock (port 5001).

POST /execute -> starts a pytest run (background), returns {"run_id", "status"}.
GET  /runs/{run_id} -> status + summary parsed from JUnit XML.
GET  /reports/{run_id} -> the JUnit XML report.
GET  /reports/{run_id}/html -> pytest HTML report if generated.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import settings

app = FastAPI(
    title="API Test Framework",
    description="Runs the pytest suite against the weather mock API and reports results.",
    version="1.0.0",
)

RUNS_DIR = Path(settings.runs_dir)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
TESTS_DIR = Path(settings.tests_dir)


class ExecuteRequest(BaseModel):
    environment: str = "qa"
    branch: str = "develop"
    commit_sha: str = ""
    tags: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_run(run_id: str) -> dict[str, Any] | None:
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _save_run(run: dict[str, Any]) -> None:
    (RUNS_DIR / f"{run['run_id']}.json").write_text(json.dumps(run, indent=2))


def _parse_junit(xml_path: Path) -> dict[str, Any]:
    root = ET.parse(xml_path).getroot()
    summary = {
        "tests_total": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0,
    }
    cases = []
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    for suite in suites:
        for attr, key in (("tests", "tests_total"), ("failures", "failures"),
                          ("errors", "errors"), ("skipped", "skipped"), ("time", "time")):
            summary[key] += int(float(suite.attrib.get(attr, 0)))
        for case in suite.findall("testcase"):
            status = "PASSED"
            detail = ""
            for child in case:
                if child.tag in ("failure", "error"):
                    status = "FAILED" if child.tag == "failure" else "ERROR"
                    detail = (child.attrib.get("message") or "")[:2000]
                    break
                if child.tag == "skipped":
                    status = "SKIPPED"
                    break
            cases.append(
                {
                    "name": case.attrib.get("name", ""),
                    "classname": case.attrib.get("classname", ""),
                    "status": status,
                    "time": float(case.attrib.get("time", 0.0)),
                    "detail": detail,
                }
            )
    summary["cases"] = cases
    summary["passed"] = summary["tests_total"] - summary["failures"] - summary["errors"] - summary["skipped"]
    return summary


def _run_pytest(run_id: str, environment: str, branch: str, commit_sha: str, tags: str | None) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    junit = run_dir / "junit.xml"
    html = run_dir / "report.html"

    env = {
        **settings.env_overrides(),
        "WEATHER_URL": settings.weather_url,
        "WEATHER_TIMEOUT": str(settings.weather_timeout),
        "TEST_ENVIRONMENT": environment,
        "TEST_BRANCH": branch,
        "TEST_COMMIT_SHA": commit_sha,
    }
    cmd = [
        settings.python_bin, "-m", "pytest", str(TESTS_DIR),
        f"--junitxml={junit}",
        "-p", "no:cacheprovider",
    ]
    try:
        import pytest_html  # noqa: F401
        cmd += [f"--html={html}", "--self-contained-html"]
    except ImportError:
        pass
    if tags:
        cmd += ["-m", tags]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, env=env, timeout=settings.run_timeout
    )
    summary = _parse_junit(junit) if junit.exists() else {"tests_total": 0, "failures": 1, "errors": 1, "skipped": 0, "passed": 0, "cases": []}
    _save_run(
        {
            "run_id": run_id,
            "status": "COMPLETED",
            "environment": environment,
            "branch": branch,
            "commit_sha": commit_sha,
            "started_at": _load_run(run_id)["started_at"],
            "finished_at": _now(),
            "summary": summary,
            "junit": str(junit),
            "html": str(html),
            "stdout_tail": proc.stdout[-2000:],
        }
    )


def _run_in_background(run_id: str, req: ExecuteRequest, tags: str | None) -> None:
    threading.Thread(
        target=_run_pytest, daemon=True,
        args=(run_id, req.environment, req.branch, req.commit_sha, tags),
    ).start()


@app.get("/")
def index():
    return {
        "service": "api-test-framework",
        "weather_url": settings.weather_url,
        "tests_dir": str(TESTS_DIR),
        "docs": "/docs",
        "execute": "POST /execute",
        "runs": "GET /runs",
        "run_detail": "GET /runs/{run_id}",
        "reports": "GET /reports/{run_id}",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "api-test-framework"}


@app.get("/tests")
def list_tests():
    env = {**settings.env_overrides(), "WEATHER_URL": settings.weather_url}
    proc = subprocess.run(
        [settings.python_bin, "-m", "pytest", str(TESTS_DIR), "--collect-only", "-q", "-p", "no:cacheprovider"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    names = [l for l in proc.stdout.splitlines() if l and not l.startswith(" ") and "::" in l]
    return {"count": len(names), "tests": names}


@app.post("/execute")
def execute(req: ExecuteRequest):
    run_id = f"api-run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{abs(hash((req.branch, req.commit_sha, req.environment))) % 1000:03d}"
    _save_run(
        {
            "run_id": run_id,
            "status": "RUNNING",
            "environment": req.environment,
            "branch": req.branch,
            "commit_sha": req.commit_sha,
            "started_at": _now(),
            "finished_at": None,
            "summary": None,
        }
    )
    _run_in_background(run_id, req, req.tags)
    return {"run_id": run_id, "status": "RUNNING"}


@app.get("/runs")
def list_runs():
    runs = []
    for path in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        data = json.loads(path.read_text())
        summary = data.get("summary") or {}
        runs.append(
            {
                "run_id": data["run_id"],
                "status": data["status"],
                "environment": data.get("environment"),
                "branch": data.get("branch"),
                "started_at": data.get("started_at"),
                "finished_at": data.get("finished_at"),
                "total": summary.get("tests_total", 0),
                "passed": summary.get("passed", 0),
                "failed": summary.get("failures", 0) + summary.get("errors", 0),
                "skipped": summary.get("skipped", 0),
            }
        )
    return {"runs": runs[: settings.max_runs]}


@app.get("/runs/{run_id}")
def run_detail(run_id: str):
    run = _load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/reports/{run_id}")
def report(run_id: str):
    run = _load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    junit = Path(run.get("junit", ""))
    if not junit.exists():
        raise HTTPException(status_code=404, detail="no junit report yet")
    return FileResponse(junit)


@app.get("/reports/{run_id}/html")
def report_html(run_id: str):
    run = _load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    html = Path(run.get("html", ""))
    if not html.exists():
        raise HTTPException(status_code=404, detail="no html report yet")
    return FileResponse(html)
