"""
Wraps two LLMGateway providers: tries `primary`, and on any exception (a
transient provider outage - the concrete case this exists for is Gemini
returning "503 UNAVAILABLE / high demand" - see the 2026-09-01 incident)
retries once with `secondary` before giving up. get_gateway() in
apps/api/orchestrator.py is called fresh per request (no shared state across
candidates), so wrapping it here doesn't change that.

Deliberately catches a bare Exception rather than a specific provider SDK's
error type - GeminiGateway, AnthropicGateway, and OpenAIGateway each raise
their own SDK's exception classes, and this wrapper is meant to survive
whichever provider is in the `primary` slot without needing to know its
internals.
"""
from __future__ import annotations

import logging

from roundzero.llm.gateway import LLMGateway

logger = logging.getLogger("roundzero.llm.fallback")


class FallbackLLMGateway(LLMGateway):
    def __init__(self, primary: LLMGateway, secondary: LLMGateway):
        self._primary = primary
        self._secondary = secondary

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        try:
            return self._primary.complete_json(system=system, user_message=user_message, max_tokens=max_tokens)
        except Exception:
            logger.warning(
                "Primary LLM gateway (%s) failed - falling back to %s.",
                type(self._primary).__name__,
                type(self._secondary).__name__,
                exc_info=True,
            )
            return self._secondary.complete_json(system=system, user_message=user_message, max_tokens=max_tokens)
