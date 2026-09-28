"""
Anthropic adapter for the LLM gateway. Reads ANTHROPIC_API_KEY from the environment
(see .env.example). Model id is configurable via ROUNDZERO_LLM_MODEL rather than
hard-coded, since model ids change over time - set it to whatever current Claude
model id your account has access to.
"""
from __future__ import annotations

import os

import anthropic

from roundzero.llm.gateway import LLMGateway

DEFAULT_MODEL_ENV_VAR = "ROUNDZERO_LLM_MODEL"
DEFAULT_MODEL_FALLBACK = "claude-sonnet-4-5"


class AnthropicGateway(LLMGateway):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model or os.environ.get(DEFAULT_MODEL_ENV_VAR, DEFAULT_MODEL_FALLBACK)

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
