"""Structured-output schemas produced by LLM providers (and validated by services)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AcoverageItem(BaseModel):
    criterion: str
    has_test: bool = False
    reuse_candidates: list[str] = Field(default_factory=list)
    suggested_new_scenarios: list[str] = Field(default_factory=list)


class ProposedTest(BaseModel):
    title: str
    framework: str = Field(pattern="^(api|ui|both)$")
    scenario: str = ""
    expected: str = ""
    acceptance_criterion_index: int | None = None


class StoryAnalysis(BaseModel):
    is_new_functionality: bool = False
    summary: str = ""
    ac_coverage: list[AcoverageItem] = Field(default_factory=list)
    reuse: list[str] = Field(default_factory=list)
    new_tests: list[ProposedTest] = Field(default_factory=list)
    redundant: list[str] = Field(default_factory=list)
    coverage_pct: float = Field(ge=0.0, le=100.0)
    status: str = Field(pattern="^(COVERED|PARTIALLY_COVERED|NOT_COVERED|REVIEW_REQUIRED)$")
    risks: list[str] = Field(default_factory=list)


class GeneratedTestFile(BaseModel):
    framework: str = Field(pattern="^(api|ui)$")
    path: str = ""
    title: str = ""
    content: str = ""


class GeneratedTests(BaseModel):
    tests: list[GeneratedTestFile] = Field(default_factory=list)


class FailureExplanation(BaseModel):
    summary: str = ""
    likely_cause: str = ""
    suggestions: list[str] = Field(default_factory=list)


class ExecutiveSummary(BaseModel):
    headline: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
