"""
Gemini adapter for the LLM gateway. Reads GEMINI_API_KEY (see .env.example).
Locked V1 stack: Gemini stays the live interviewer model - kept at full Flash,
not Flash-Lite, since interviewer/adaptive-probing quality is the
highest-leverage thing to get right in this slice
(specs/001-ml-system-design-vertical-slice/plan.md). Flash-Lite is reserved for
cheap structured extraction if/when that becomes its own LLM call.

Default model bumped 2026-09 from gemini-2.5-flash to gemini-3.6-flash: Google
retired 2.5 Flash for new API keys/projects (a fresh AI Studio key started
getting `404 NOT_FOUND ... This model models/gemini-2.5-flash is no longer
available to new users`) - override via ROUNDZERO_GEMINI_MODEL if a project
still has 2.5 Flash access and wants to keep using it.
"""
from __future__ import annotations

import os

from google import genai
from google.genai import types

from roundzero.llm.gateway import LLMGateway

DEFAULT_MODEL_ENV_VAR = "ROUNDZERO_GEMINI_MODEL"
DEFAULT_MODEL_FALLBACK = "gemini-3.6-flash"


# The SDK's default HttpOptions has timeout=None - an unbounded wait if
# Gemini is slow to respond (as opposed to failing fast with a 503, which is
# already quick). Observed live during a 2026-09-01 Gemini outage: with no
# cap, a stalled request can sit for a long time before anything - including
# FallbackLLMGateway - gets a chance to react, which is especially bad for a
# live voice call where the candidate is waiting in silence.
_REQUEST_TIMEOUT_MS = 10_000


class GeminiGateway(LLMGateway):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self._client = genai.Client(
            api_key=api_key or os.environ.get("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS),
        )
        self._model = model or os.environ.get(DEFAULT_MODEL_ENV_VAR, DEFAULT_MODEL_FALLBACK)

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                max_output_tokens=max_tokens,
            ),
        )
        return response.text
