"""OpenAI-compatible chat provider.

Works with OpenAI, OpenCode-compatible endpoints, Ollama, LM Studio, vLLM, etc.
The endpoint is configured via LLM_BASE_URL; no provider SDK is used.
"""
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

logger = logging.getLogger("app.llm.openai_compat")

_PROMPTS = {
    StoryAnalysis: (
        "Analyze the test coverage of the given user story. Return JSON conforming "
        "to this schema, strictly as JSON with no markdown fences."
    ),
    GeneratedTests: (
        "Generate automated test files for the missing acceptance criteria. Return "
        "JSON conforming to this schema (each entry: framework api|ui, path relative "
        "to the test suite root, content is a complete test file)."
    ),
    FailureExplanation: (
        "Explain the following test failure concisely. Return JSON conforming to this schema."
    ),
    ExecutiveSummary: (
        "Write a concise executive summary of these QA metrics for management. "
        "Return JSON conforming to this schema."
    ),
}


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self._base_url = (base_url or settings.llm_base_url).rstrip("/")
        self._api_key = api_key or settings.llm_api_key
        self._model = model or settings.llm_model or "gpt-4o-mini"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _chat(self, messages: list[dict[str, str]], *, temperature: float = 0.0,
                    response_format: dict | None = None) -> str:
        url = f"{self._base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as exc:
            logger.warning("LLM request failed: %s", exc)
            raise

    async def structured(self, *, messages: list[dict[str, str]],
                         schema: type[BaseModel], temperature: float = 0.0) -> BaseModel:
        schema_messages = list(messages)
        instruction = _PROMPTS.get(schema, "Return JSON conforming to the schema.")
        schema_messages.append(
            {"role": "system", "content": f"{instruction}\nSchema:\n{schema.model_json_schema()}"}
        )
        raw = await self._chat(schema_messages, temperature=temperature,
                               response_format={"type": "json_object"})
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned non-JSON output")
            raise ValueError(f"invalid JSON from LLM: {exc}") from exc
        return validate_or_raise(schema, data)

    async def analyze_story(self, story: dict[str, Any]) -> StoryAnalysis:
        return await self._analyze_story(story)

    async def _analyze_story(self, story: dict[str, Any]) -> StoryAnalysis:
        import json as _json

        content = _json.dumps(story, default=str)
        result = await self.structured(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Story data:\n{content[:12000]}"},
            ],
            schema=StoryAnalysis,
        )
        return StoryAnalysis.model_validate(result.model_dump())

    async def generate_test_cases(self, request: dict[str, Any]) -> GeneratedTests:
        import json as _json

        content = _json.dumps(request, default=str)
        result = await self.structured(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Generation request:\n{content[:12000]}"},
            ],
            schema=GeneratedTests,
        )
        return GeneratedTests.model_validate(result.model_dump())

    async def explain_failure(self, context: dict[str, Any]) -> FailureExplanation:
        import json as _json

        content = _json.dumps(context, default=str)
        result = await self.structured(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Failure context:\n{content[:8000]}"},
            ],
            schema=FailureExplanation,
        )
        return FailureExplanation.model_validate(result.model_dump())

    async def executive_summary(self, metrics: dict[str, Any]) -> ExecutiveSummary:
        import json as _json

        content = _json.dumps(metrics, default=str)
        result = await self.structured(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Metrics:\n{content[:12000]}"},
            ],
            schema=ExecutiveSummary,
        )
        return ExecutiveSummary.model_validate(result.model_dump())
