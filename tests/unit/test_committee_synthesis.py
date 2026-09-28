"""
src/roundzero/debrief/committee.py - specs/002-full-loop-platform P0.6. Covers
the deterministic math (never LLM-judged - overall_readiness_pct/hire_signal/
confidence), the rule-based no-key fallback, and llm_committee_synthesis's
happy path plus its fallback-on-malformed-response behavior. No network
dependency, same convention as test_fallback_llm_gateway.py's FakeGateway.
"""
from __future__ import annotations

from roundzero.debrief.committee import (
    _confidence_for,
    _overall_readiness,
    llm_committee_synthesis,
    rule_based_committee_synthesis,
)
from roundzero.evaluation.models import DimensionScore, RoundEvaluation
from roundzero.leveling.calibration import calibrate_level
from roundzero.llm.gateway import LLMGateway


class FakeGateway(LLMGateway):
    def __init__(self, *, response: str = "{}"):
        self.response = response
        self.calls = 0

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        self.calls += 1
        return self.response


def _evaluation(round_id: str, pct: int, signal: str, dims: list[DimensionScore]) -> RoundEvaluation:
    return RoundEvaluation(
        round_id=round_id,
        dimension_scores=dims,
        readiness_pct=pct,
        hire_signal=signal,
        primary_concern="fixture concern",
        strengths=[],
        weaknesses=[],
        improvement_plan=[],
        level_calibration=calibrate_level(pct, signal),
    )


def _sample_rounds() -> list[tuple[str, RoundEvaluation]]:
    d1 = [DimensionScore(dimension="reliability", label="Reliability", weight=1.0, score=3, evidence_narrative="handled failure modes well")]
    d2 = [DimensionScore(dimension="coding_correctness", label="Correctness", weight=1.0, score=2, evidence_narrative="missed an edge case")]
    return [
        ("ml_system_design", _evaluation("r1", 70, "HIRE", d1)),
        ("coding", _evaluation("r2", 50, "LEAN HIRE", d2)),
    ]


def test_overall_readiness_is_the_mean_of_the_round_percentages():
    pct, signal = _overall_readiness([ev for _, ev in _sample_rounds()])
    assert pct == 60
    assert signal == "LEAN HIRE"


def test_confidence_is_medium_at_two_rounds_and_high_at_three_or_more():
    assert _confidence_for(2) == "medium"
    assert _confidence_for(3) == "high"
    assert _confidence_for(5) == "high"


def test_rule_based_synthesis_never_calls_an_llm_and_stays_grounded_in_the_given_evidence():
    report = rule_based_committee_synthesis(_sample_rounds(), "Senior ML Engineer")
    assert report.overall_readiness_pct == 60
    assert report.overall_hire_signal == "LEAN HIRE"
    assert report.confidence == "medium"
    assert any("ML System Design" in s for s in report.strengths)
    assert any("handled failure modes well" in e for e in report.key_evidence)


def test_llm_committee_synthesis_happy_path_uses_the_llms_prose_but_deterministic_numbers():
    import json

    gateway = FakeGateway(
        response=json.dumps(
            {
                "headline": "Consistent strength in system design, weaker on implementation.",
                "strengths": ["Handles ambiguity well", "Strong on reliability"],
                "concerns": ["Coding correctness needs work"],
                "level_signal": "Trending at target level overall.",
                "key_evidence": ["System Design round: handled failure modes well"],
            }
        )
    )
    report = llm_committee_synthesis(gateway, _sample_rounds(), "Senior ML Engineer")
    assert gateway.calls == 1
    # Numbers are still the deterministic ones, never taken from the LLM response.
    assert report.overall_readiness_pct == 60
    assert report.overall_hire_signal == "LEAN HIRE"
    assert report.confidence == "medium"
    assert report.headline.startswith("Consistent strength")
    assert report.concerns == ["Coding correctness needs work"]


def test_llm_committee_synthesis_falls_back_to_rule_based_on_malformed_json():
    gateway = FakeGateway(response="not valid json at all")
    report = llm_committee_synthesis(gateway, _sample_rounds(), "Senior ML Engineer")
    assert gateway.calls == 1
    # Same deterministic numbers as the rule-based path, and a rule-based headline.
    assert report.overall_readiness_pct == 60
    assert "Rule-based summary" in report.headline


def test_llm_committee_synthesis_falls_back_when_required_fields_are_missing():
    import json

    gateway = FakeGateway(response=json.dumps({"headline": "Looks fine", "strengths": [], "concerns": [], "level_signal": ""}))
    report = llm_committee_synthesis(gateway, _sample_rounds(), "Senior ML Engineer")
    assert "Rule-based summary" in report.headline
