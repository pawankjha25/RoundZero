"""
src/roundzero/prep_plan/suggest.py - user-pitched Prep Plans feature (not
from the P0 backlog). Covers the bank-based fallback (used with no LLM key,
and unconditionally for Coding areas), and llm_suggest_questions' happy path
plus its fallback-on-malformed/empty response - same shape as
test_real_interview_structuring.py's FakeGateway convention.
"""
from __future__ import annotations

import json

from roundzero.domain.interview import TargetRole
from roundzero.llm.gateway import LLMGateway
from roundzero.prep_plan.suggest import (
    FREEFORM_ROUND_TYPES,
    filter_bank_scenarios,
    llm_suggest_questions,
    suggest_questions_from_bank,
)


class FakeGateway(LLMGateway):
    def __init__(self, *, response: str = "{}"):
        self.response = response
        self.calls = 0

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        self.calls += 1
        return self.response


STAFF_ML_INFRA = TargetRole(role_family="ml_engineer", level="staff", domain="ml_infra", company_profile="generic")


def test_coding_is_not_a_freeform_round_type():
    assert "coding" not in FREEFORM_ROUND_TYPES
    assert "ml_system_design" in FREEFORM_ROUND_TYPES
    assert "ml_depth" in FREEFORM_ROUND_TYPES


def test_filter_bank_scenarios_matches_level_and_domain_and_excludes_given_ids():
    pool = filter_bank_scenarios("ml_system_design", STAFF_ML_INFRA)
    ids = {s.get("id", s.get("name")) for s in pool}
    assert "multi_tenant_inference_platform" in ids

    pool_excluded = filter_bank_scenarios(
        "ml_system_design", STAFF_ML_INFRA, exclude_scenario_ids=frozenset({"multi_tenant_inference_platform"})
    )
    ids_excluded = {s.get("id", s.get("name")) for s in pool_excluded}
    assert "multi_tenant_inference_platform" not in ids_excluded


def test_suggest_questions_from_bank_never_calls_an_llm_and_returns_real_scenarios():
    suggestions = suggest_questions_from_bank("coding", STAFF_ML_INFRA)
    assert 0 < len(suggestions) <= 5
    assert all(s.scenario_id for s in suggestions)
    assert all(s.prompt for s in suggestions)


def test_suggest_questions_from_bank_excludes_already_added_scenarios():
    pool = filter_bank_scenarios("ml_system_design", STAFF_ML_INFRA)
    already_added = frozenset(s.get("id", s.get("name")) for s in pool)
    suggestions = suggest_questions_from_bank("ml_system_design", STAFF_ML_INFRA, already_added)
    # Every matching scenario was excluded, so the progressive relax falls
    # all the way back to "ignore exclude" rather than returning nothing -
    # same never-empty-if-the-bank-has-anything behavior pick_scenario has.
    assert len(suggestions) > 0


def test_llm_suggest_questions_happy_path_uses_the_llms_suggestions():
    payload = json.dumps(
        {
            "questions": [
                {"prompt": "Design a feature store for a recsys.", "notes": "probes online/offline skew"},
                {"prompt": "How would you version ML models in production?", "notes": ""},
            ]
        }
    )
    gateway = FakeGateway(response=payload)
    result = llm_suggest_questions(gateway, "ml_system_design", STAFF_ML_INFRA, existing_prompts=["some other question"])

    assert gateway.calls == 1
    assert len(result) == 2
    assert result[0].prompt == "Design a feature store for a recsys."
    assert result[0].scenario_id is None
    assert result[1].notes == ""


def test_llm_suggest_questions_falls_back_to_bank_on_malformed_json():
    gateway = FakeGateway(response="not valid json at all")
    result = llm_suggest_questions(gateway, "ml_system_design", STAFF_ML_INFRA, existing_prompts=[])
    assert len(result) > 0
    assert all(s.scenario_id for s in result)  # bank fallback always carries a scenario_id


def test_llm_suggest_questions_falls_back_when_questions_list_is_empty():
    gateway = FakeGateway(response=json.dumps({"questions": []}))
    result = llm_suggest_questions(gateway, "ml_depth", STAFF_ML_INFRA, existing_prompts=[])
    assert len(result) > 0
    assert all(s.scenario_id for s in result)
