"""
OpenAI adapter for the LLM gateway. Reads OPENAI_API_KEY (see .env.example).
Locked V1 stack: GPT-5 mini is the independent evaluator and report/improvement
writer - a different vendor from the Gemini interviewer on purpose, so a
systematic blind spot in one model family doesn't show up in both the asking and
the grading (CLAUDE.md decision 4: interviewing and evaluation are separate
concerns - taken one step further, separate vendors).

GPT-5 mini is a reasoning model: on the Chat Completions API, reasoning tokens
are deducted from `max_completion_tokens` before any output tokens, and at the
default "medium" effort a small budget (e.g. src/roundzero/debrief/synthesis.py's
1024) can be entirely consumed by reasoning, leaving `message.content` as ""
(discovered 2026-09 - llm_report_synthesis's json.loads(raw) blew up on that
empty string). Pinning reasoning_effort="low" here keeps these short
structured-JSON calls (score-with-evidence, prose synthesis) from eating their
own output budget; callers should still leave real headroom in max_tokens.
"""
from __future__ import annotations

import os

from openai import OpenAI

from roundzero.llm.gateway import LLMGateway

DEFAULT_MODEL_ENV_VAR = "ROUNDZERO_OPENAI_MODEL"
DEFAULT_MODEL_FALLBACK = "gpt-5-mini"
DEFAULT_REASONING_EFFORT = "low"


class OpenAIGateway(LLMGateway):
    def __init__(self, model: str | None = None, api_key: str | None = None, reasoning_effort: str | None = None):
        self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self._model = model or os.environ.get(DEFAULT_MODEL_ENV_VAR, DEFAULT_MODEL_FALLBACK)
        self._reasoning_effort = reasoning_effort or DEFAULT_REASONING_EFFORT

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_completion_tokens=max_tokens,
            response_format={"type": "json_object"},
            reasoning_effort=self._reasoning_effort,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            finish_reason = response.choices[0].finish_reason
            raise RuntimeError(
                f"OpenAIGateway: empty completion from {self._model} (finish_reason="
                f"{finish_reason!r}) - likely max_completion_tokens={max_tokens} was too "
                "low for this call's reasoning + output, even at reasoning_effort="
                f"{self._reasoning_effort!r}."
            )
        return content
