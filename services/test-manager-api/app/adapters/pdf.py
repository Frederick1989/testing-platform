"""PDF generation: HTML -> PDF via a pluggable engine (WeasyPrint default)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from app.config import settings

logger = logging.getLogger("app.pdf")


class PDFEngine(Protocol):
    def convert(self, html: str, dest: Path) -> Path: ...


class WeasyPrintEngine:
    name = "weasyprint"

    def __init__(self) -> None:
        try:
            from weasyprint import HTML  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "weasyprint is not installed; install system libs (libpango etc.) "
                "and pip package, or set REPORT_ENGINE=manual"
            ) from exc

    def convert(self, html: str, dest: Path) -> Path:
        from weasyprint import HTML

        dest.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html).write_pdf(dest)
        return dest


class ManualEngine:
    """Writes the HTML file only (no PDF). Useful when weasyprint is unavailable."""

    name = "manual"

    def convert(self, html: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        return dest


def build_pdf_engine() -> PDFEngine:
    engine = (settings.report_engine or "weasyprint").lower()
    if engine == "manual":
        logger.warning("PDF engine set to manual: HTML only, no PDF rendering")
        return ManualEngine()
    try:
        return WeasyPrintEngine()
    except RuntimeError as exc:
        logger.error("WeasyPrint unavailable (%s); using manual engine", exc)
        return ManualEngine()
