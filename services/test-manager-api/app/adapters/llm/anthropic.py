"""Anthropic Messages API provider."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import settings
from app.schemas.llm import (
    ExecutiveSummary,
    FailureExplanation,
    GeneratedTests,
    StoryAnalysis,
)

from .base import SYSTEM_PROMPT, validate_or_raise

logger = logging.getLogger("app.llm.anthropic")

_PROMPTS = {
    StoryAnalysis: "Analyze the test coverage of the given user story.",
    GeneratedTests: "Generate automated test files for the missing acceptance criteria.",
    FailureExplanation: "Explain the following test failure concisely.",
    ExecutiveSummary: "Write a concise executive summary of these QA metrics.",
}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.llm_api_key
        self._model = model or settings.llm_model or "claude-3-5-haiku-latest"

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

    async def _chat(self, messages: list[dict[str, str]]) -> str:
        system = SYSTEM_PROMPT
        user_parts = []
        for m in messages:
            if m["role"] == "system":
                system += "\n" + m["content"]
            else:
                user_parts.append(m["content"])
        payload = {
            "model": self._model,
            "system": system,
            "messages": [{"role": "user", "content": "\n\n".join(user_parts)}],
            "max_tokens": 4096,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            return "".join(b["text"] for b in data["content"] if b["type"] == "text")
        except httpx.HTTPError as exc:
            logger.warning("Anthropic request failed: %s", exc)
            raise

    async def structured(self, *, messages: list[dict[str, str]],
                         schema: type[BaseModel], temperature: float = 0.0) -> BaseModel:
        content_messages = list(messages)
        content_messages.append(
            {
                "role": "system",
                "content": (
                    f"{_PROMPTS.get(schema, 'Return JSON conforming to the schema.')}\n"
                    f"Return strictly valid JSON matching this schema, no markdown:\n"
                    f"{schema.model_json_schema()}"
                ),
            }
        )
        raw = await self._chat(content_messages)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1].removeprefix("json").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON from LLM: {exc}") from exc
        return validate_or_raise(schema, data)

    async def analyze_story(self, story: dict[str, Any]) -> StoryAnalysis:
        import json as _json

        result = await self.structured(
            messages=[{"role": "user", "content": _json.dumps(story, default=str)[:12000]}],
            schema=StoryAnalysis,
        )
        return StoryAnalysis.model_validate(result.model_dump())

    async def generate_test_cases(self, request: dict[str, Any]) -> GeneratedTests:
        import json as _json

        result = await self.structured(
            messages=[{"role": "user", "content": _json.dumps(request, default=str)[:12000]}],
            schema=GeneratedTests,
        )
        return GeneratedTests.model_validate(result.model_dump())

    async def explain_failure(self, context: dict[str, Any]) -> FailureExplanation:
        import json as _json

        result = await self.structured(
            messages=[{"role": "user", "content": _json.dumps(context, default=str)[:8000]}],
            schema=FailureExplanation,
        )
        return FailureExplanation.model_validate(result.model_dump())

    async def executive_summary(self, metrics: dict[str, Any]) -> ExecutiveSummary:
        import json as _json

        result = await self.structured(
            messages=[{"role": "user", "content": _json.dumps(metrics, default=str)[:12000]}],
            schema=ExecutiveSummary,
        )
        return ExecutiveSummary.model_validate(result.model_dump())
