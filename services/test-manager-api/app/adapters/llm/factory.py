"""LLM provider factory with graceful fallback."""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings

from .anthropic import AnthropicProvider
from .base import LLMProvider
from .heuristic import HeuristicLLMProvider
from .openai_compat import OpenAICompatibleProvider

logger = logging.getLogger("app.llm.factory")

_PROVIDER_ALIASES = {
    "none": None,
    "heuristic": "heuristic",
    "openai": "openai_compatible",
    "openai_compatible": "openai_compatible",
    "opencode": "openai_compatible",
    "local": "openai_compatible",
    "ollama": "openai_compatible",
    "anthropic": "anthropic",
}


def build_provider() -> LLMProvider:
    raw = (settings.llm_provider or "none").strip().lower()
    kind = _PROVIDER_ALIASES.get(raw, None)
    if kind is None:
        logger.warning(
            "Unknown LLM_PROVIDER=%r, falling back to deterministic heuristic provider",
            raw,
        )
        return HeuristicLLMProvider()
    if kind == "heuristic":
        logger.info("Using deterministic heuristic provider (no LLM configured)")
        return HeuristicLLMProvider()
    if kind == "anthropic":
        return AnthropicProvider()
    return OpenAICompatibleProvider()


def describe(provider: LLMProvider) -> dict[str, Any]:
    return {
        "provider": settings.llm_provider,
        "implementation": getattr(provider, "name", type(provider).__name__),
        "model": settings.llm_model or "default",
        "base_url": settings.llm_base_url or "",
    }
