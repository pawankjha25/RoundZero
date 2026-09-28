"""
src/roundzero/debrief/real_interview.py - specs/002-full-loop-platform P0.11.
Covers the rule-based no-key fallback (never fabricates a per-round
breakdown it can't derive), and llm_structure_experience's happy path plus
its fallback-on-malformed/empty response. No network dependency, same
convention as test_committee_synthesis.py's FakeGateway.
"""
from __future__ import annotations

import json

from roundzero.debrief.real_interview import (
    llm_structure_experience,
    rule_based_structure_experience,
)
from roundzero.llm.gateway import LLMGateway


class FakeGateway(LLMGateway):
    def __init__(self, *, response: str = "{}"):
        self.response = response
        self.calls = 0

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        self.calls += 1
        return self.response


def test_rule_based_never_calls_an_llm_and_carries_the_raw_text_forward_verbatim():
    raw = "First round was a system design question about a rate limiter. Went okay I think."
    result = rule_based_structure_experience(raw)
    assert len(result.rounds) == 1
    assert result.rounds[0].round_type_label == "Not broken down"
    assert raw in result.rounds[0].question_family
    assert result.self_assessment == ""


def test_rule_based_returns_no_rounds_for_blank_input():
    result = rule_based_structure_experience("   ")
    assert result.rounds == []


def test_llm_structure_experience_happy_path_uses_the_llms_breakdown():
    payload = json.dumps(
        {
            "rounds": [
                {
                    "round_type_label": "System Design",
                    "question_family": "Design a rate limiter",
                    "follow_ups": "How would you handle a hot key?",
                    "difficulty": "medium",
                },
                {
                    "round_type_label": "Coding",
                    "question_family": "Graph traversal problem",
                    "follow_ups": "",
                    "difficulty": "",
                },
            ],
            "self_assessment": "Felt strong on design, shaky on the coding round.",
        }
    )
    gateway = FakeGateway(response=payload)
    result = llm_structure_experience(gateway, "some raw notes", hints="Staff ML Infra, Anthropic")

    assert gateway.calls == 1
    assert len(result.rounds) == 2
    assert result.rounds[0].round_type_label == "System Design"
    assert result.rounds[1].question_family == "Graph traversal problem"
    assert result.self_assessment == "Felt strong on design, shaky on the coding round."


def test_llm_structure_experience_falls_back_to_rule_based_on_malformed_json():
    gateway = FakeGateway(response="not valid json at all")
    result = llm_structure_experience(gateway, "raw notes here")
    assert len(result.rounds) == 1
    assert result.rounds[0].round_type_label == "Not broken down"


def test_llm_structure_experience_falls_back_when_rounds_list_is_empty():
    gateway = FakeGateway(response=json.dumps({"rounds": [], "self_assessment": "n/a"}))
    result = llm_structure_experience(gateway, "raw notes here")
    assert len(result.rounds) == 1
    assert result.rounds[0].round_type_label == "Not broken down"
