"""
roundzero.llm.providers.fallback_provider.FallbackLLMGateway - added
2026-09-01 after a live Gemini "503 UNAVAILABLE / high demand" outage stalled
a voice round. No live network - both providers here are small in-test fakes.
"""
from __future__ import annotations

import pytest

from roundzero.llm.gateway import LLMGateway
from roundzero.llm.providers.fallback_provider import FallbackLLMGateway


class FakeGateway(LLMGateway):
    def __init__(self, *, fails: bool = False, response: str = "ok"):
        self.fails = fails
        self.response = response
        self.calls = 0

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        self.calls += 1
        if self.fails:
            raise RuntimeError("simulated transient provider outage")
        return self.response


def test_uses_primary_when_it_succeeds():
    primary = FakeGateway(response="from primary")
    secondary = FakeGateway(response="from secondary")
    gateway = FallbackLLMGateway(primary, secondary)

    result = gateway.complete_json(system="sys", user_message="hi")

    assert result == "from primary"
    assert primary.calls == 1
    assert secondary.calls == 0


def test_falls_back_to_secondary_when_primary_raises():
    primary = FakeGateway(fails=True)
    secondary = FakeGateway(response="from secondary")
    gateway = FallbackLLMGateway(primary, secondary)

    result = gateway.complete_json(system="sys", user_message="hi")

    assert result == "from secondary"
    assert primary.calls == 1
    assert secondary.calls == 1


def test_propagates_if_both_fail():
    primary = FakeGateway(fails=True)
    secondary = FakeGateway(fails=True)
    gateway = FallbackLLMGateway(primary, secondary)

    with pytest.raises(RuntimeError):
        gateway.complete_json(system="sys", user_message="hi")
