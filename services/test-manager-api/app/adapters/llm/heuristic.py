"""Deterministic, rule-based LLM provider used when no model is configured.

It is a real provider: it always returns schema-valid output and never fails,
which keeps every AI-augmented workflow functional without an LLM. Accuracy is
lower than a real model; it is intentionally conservative (it flags REVIEW_REQUIRED
whenever it has to guess).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel

from app.schemas.llm import (
    AcoverageItem,
    ExecutiveSummary,
    FailureExplanation,
    GeneratedTestFile,
    GeneratedTests,
    ProposedTest,
    StoryAnalysis,
)

logger = logging.getLogger("app.llm.heuristic")

_STATUS_COVERED = "COVERED"
_STATUS_REVIEW = "REVIEW_REQUIRED"

_FRAMEWORK_HINTS: dict[str, str] = {
    "click": "ui",
    "button": "ui",
    "page": "ui",
    "display": "ui",
    "login": "both",
    "search": "both",
    "valid": "both",
    "invalid": "both",
    "endpoint": "api",
    "api": "api",
    "response": "api",
    "status code": "api",
}


def _guess_framework(text: str) -> str:
    lower = text.lower()
    for hint, fw in _FRAMEWORK_HINTS.items():
        if hint in lower:
            return fw
    return "both"


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug[:40] or "test"


class HeuristicLLMProvider:
    name = "heuristic"

    async def structured(self, *, messages: list[dict[str, str]],
                         schema: type[BaseModel], temperature: float = 0.0) -> BaseModel:
        raise NotImplementedError("heuristic provider is used for specific tasks")

    async def analyze_story(self, story: dict[str, Any]) -> StoryAnalysis:
        acs: list[str] = story.get("acceptance_criteria") or []
        existing_keys: list[str] = story.get("existing_test_keys") or []
        linked_by_ac: list[list[str]] = story.get("linked_tests_by_ac") or [[]] * len(acs)
        ac_coverage: list[AcoverageItem] = []
        covered = 0
        new_tests: list[ProposedTest] = []
        reuse: list[str] = []
        seen_reuse: set[str] = set()

        for i, ac in enumerate(acs):
            linked = linked_by_ac[i] if i < len(linked_by_ac) else []
            reuse_candidates = [k for k in existing_keys if k not in seen_reuse][:2]
            has_test = bool(linked)
            if not has_test and reuse_candidates:
                reuse.extend(reuse_candidates)
                seen_reuse.update(reuse_candidates)
            suggestions: list[str] = []
            if not has_test:
                # rule-based scenario naming from the AC text
                words = re.sub(r"[^a-zA-Z0-9 ]", " ", ac).split()
                topic = " ".join(words[:4]) if words else "the behavior"
                suggestions.append(f"Verify: {topic}")
                framework = _guess_framework(ac)
                new_tests.append(
                    ProposedTest(
                        title=f"{ac[:80]}",
                        framework=framework,
                        scenario=topic,
                        expected="behaviour matches the stated acceptance criterion",
                        acceptance_criterion_index=i,
                    )
                )
            if has_test:
                covered += 1
            ac_coverage.append(
                AcoverageItem(
                    criterion=ac,
                    has_test=has_test,
                    reuse_candidates=reuse_candidates,
                    suggested_new_scenarios=suggestions,
                )
            )

        total = max(len(acs), 1)
        coverage_pct = round(covered / total * 100, 1)
        is_new = not existing_keys and len(acs) > 0
        status = _STATUS_COVERED if coverage_pct == 100 else _STATUS_REVIEW
        risks = []
        if coverage_pct < 100:
            risks.append(f"{total - covered} acceptance criteria have no linked test case")
        return StoryAnalysis(
            is_new_functionality=is_new,
            summary=(
                f"{covered}/{total} acceptance criteria covered. "
                + ("New functionality." if is_new else "Existing functionality.")
            ),
            ac_coverage=ac_coverage,
            reuse=reuse,
            new_tests=new_tests,
            redundant=[],
            coverage_pct=coverage_pct,
            status=status,
            risks=risks,
        )

    async def generate_test_cases(self, request: dict[str, Any]) -> GeneratedTests:
        story_id = request.get("story_id")
        candidates: list[ProposedTest] = [
            ProposedTest.model_validate(c) for c in request.get("candidates", [])
        ]
        files: list[GeneratedTestFile] = []
        for c in candidates:
            slug = _slug(c.title)
            if c.framework in ("api", "both"):
                files.append(self._api_file(story_id, slug, c))
            if c.framework in ("ui", "both"):
                files.append(self._ui_file(story_id, slug, c))
        return GeneratedTests(tests=files)

    @staticmethod
    def _api_file(story_id: Any, slug: str, c: ProposedTest) -> GeneratedTestFile:
        scenario = c.scenario.replace("'", "\\'")
        content = f'''"""Generated from story {story_id}: {c.title}"""
import pytest
import httpx

BASE_URL = "http://weather:5000"


@pytest.mark.parametrize("city", ["London", "New York", "Tokyo"])
def test_story_{story_id}_{slug}_valid_city(city: str) -> None:
    """Scenario: {scenario}"""
    resp = httpx.get(f"{{BASE_URL}}/weather/{{city}}", timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    for field in ("city", "temperature_c", "condition"):
        assert field in body, f"missing field {{field}}"


def test_story_{story_id}_{slug}_invalid_city() -> None:
    resp = httpx.get(f"{{BASE_URL}}/weather/InvalidCityXYZ", timeout=10)
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_story_{story_id}_{slug}_missing_parameter() -> None:
    resp = httpx.get(f"{{BASE_URL}}/weather", timeout=10)
    assert resp.status_code == 400
'''
        return GeneratedTestFile(
            framework="api",
            path=f"tests/stories/story_{story_id}/test_{slug}.py",
            title=f"Story {story_id}: {c.title} (API)",
            content=content,
        )

    @staticmethod
    def _ui_file(story_id: Any, slug: str, c: ProposedTest) -> GeneratedTestFile:
        scenario = c.scenario.replace("'", "\\'")
        content = f'''import {{ test, expect }} from '@playwright/test';

test.describe('Story {story_id}: {c.title}', () => {{
  test('{scenario}', async ({{ page }}) => {{
    await page.goto('http://webapp:8000');
    await page.getByPlaceholder('Enter city').fill('London');
    await page.getByRole('button', {{ name: /search/i }}).click();
    await expect(page.getByTestId('weather-result')).toBeVisible();
  }});
}});
'''
        return GeneratedTestFile(
            framework="ui",
            path=f"tests/stories/story_{story_id}/{slug}.spec.ts",
            title=f"Story {story_id}: {c.title} (UI)",
            content=content,
        )

    async def explain_failure(self, context: dict[str, Any]) -> FailureExplanation:
        result = context.get("result") or {}
        return FailureExplanation(
            summary=(
                f"{result.get('title', 'Unknown test')} failed "
                f"({result.get('status', 'FAILED')})."
            ),
            likely_cause="Deterministic analysis is unavailable; inspect the stack trace and "
                         "recent commits for the affected module.",
            suggestions=["Review the stack trace", "Check recently merged PRs"],
        )

    async def executive_summary(self, metrics: dict[str, Any]) -> ExecutiveSummary:
        sprints = metrics.get("sprints") or {}
        coverage = metrics.get("coverage") or {}
        defects = metrics.get("defects") or {}
        headline = (
            f"Sprint delivery {sprints.get('completed', 0)}/"
            f"{sprints.get('committed', 0)} stories, "
            f"coverage {coverage.get('requirement', 0)}%, "
            f"{defects.get('open', 0)} open defects."
        )
        return ExecutiveSummary(
            headline=headline,
            paragraphs=[
                "This summary is generated deterministically because no LLM provider is "
                "configured. Configure LLM_PROVIDER for natural-language analysis."
            ],
            recommendations=[
                "Close coverage gaps flagged in the Test Matrix",
                "Investigate flaky tests before sign-off",
                "Resolve blocking defects before UAT",
            ],
        )
