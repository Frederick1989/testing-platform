"""Report generation: snapshot metrics -> HTML -> PDF -> archive."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.adapters.pdf import build_pdf_engine
from app.config import settings
from app.db import SessionLocal
from app.repositories import jobs as job_repo
from app.repositories import azure as az_repo
from app.services import coverage as coverage_svc
from app.services import defects as defects_svc
from app.services import flakiness as flakiness_svc
from app.services import risks as risks_svc
from app.services import sprints as sprints_svc
from app.services.readiness import list_ready_stories

logger = logging.getLogger("app.reports")

_DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "reports" / "templates"
_TEMPLATE_DIR = Path(settings.report_templates_dir) if settings.report_templates_dir else _DEFAULT_TEMPLATE_DIR


def _snapshot_metrics() -> dict[str, Any]:
    with SessionLocal() as session:
        coverage = coverage_svc.summarize(session)
        current = az_repo.get_current_iteration(session)
        sprint = sprints_svc.sprint_metrics(session, current)
        sprints = sprints_svc.list_sprint_summaries(session)
        defects = defects_svc.summary(session)
        defect_trend = defects_svc.trend(session, days=30)
        health = flakiness_svc.test_health_stats(session)
        flaky = flakiness_svc.flaky_tests(session)
        regression = flakiness_svc.regression_report(session)
        risks = risks_svc.compute_risks(session)
        ready_stories = list_ready_stories(session)
        matrix = matrix_for_report(session)
        return {
            "coverage": coverage,
            "sprint": sprint,
            "sprints": sprints,
            "defects": defects,
            "defect_trend": defect_trend,
            "test_health": health,
            "flaky": flaky,
            "regression": regression,
            "risks": risks,
            "ready_stories": ready_stories,
            "matrix": matrix,
            "generated_at": datetime.now(timezone.utc),
        }


def matrix_for_report(session: Any) -> list[dict[str, Any]]:
    from app.services.matrix import matrix_for_sprint

    return matrix_for_sprint(session)


def _render_html(data: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")
    return template.render(
        company_name=settings.report_company_name,
        primary_color=settings.report_primary_color,
        secondary_color=settings.report_secondary_color,
        footer=settings.report_footer,
        logo=settings.report_logo_path,
        **data,
    )


def generate_report(session, *, sprint: str = "", include_matrix: bool = True) -> dict[str, Any]:
    metrics = _snapshot_metrics()
    if sprint:
        metrics["sprint"]["name"] = sprint
    if not include_matrix:
        metrics["matrix"] = []

    html = _render_html(metrics)
    year = datetime.now(timezone.utc).year
    sprint_dir = (metrics["sprint"]["name"] or "all").replace("/", "-")
    out_dir = (
        Path(settings.reports_root) / str(year) / sprint_dir
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    html_path = out_dir / f"report-{stamp}.html"
    html_path.write_text(html, encoding="utf-8")

    pdf_engine = build_pdf_engine()
    pdf_path = out_dir / f"report-{stamp}.pdf"
    pdf_engine.convert(html, pdf_path)

    period_start, period_end = None, None
    if metrics["sprint"].get("start_date") and metrics["sprint"].get("finish_date"):
        period_start, period_end = metrics["sprint"]["start_date"], metrics["sprint"]["finish_date"]

    # store a JSON snapshot for historical navigation (state at time of generation)
    snapshot = {
        k: v for k, v in metrics.items()
        if k not in ("matrix",)
    }
    snapshot["generated_at"] = datetime.now(timezone.utc).isoformat()

    archive = job_repo.create_report_archive(
        session,
        title=f"UAT Report — {metrics['sprint'].get('name') or 'Overview'}",
        sprint_name=metrics["sprint"].get("name") or "",
        period_start=period_start,
        period_end=period_end,
        html_path=str(html_path),
        pdf_path=str(pdf_path),
        snapshot=snapshot,
        created_by="system",
    )
    session.commit()
    return {
        "archive_id": archive.id,
        "title": archive.title,
        "html_path": str(html_path),
        "pdf_path": str(pdf_path),
        "snapshot": snapshot,
    }
