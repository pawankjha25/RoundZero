"""
Smoke test for the Backend System Design interviewer agent plumbing - domain
contracts, prompt/scenario loader, and agent turn logic - using a fake LLM
gateway so it runs with no API key and no network. Mirrors
test_ml_system_design_agent_smoke.py's exact shape; does not judge interview
*quality* (that needs the CLI harness and a real model), only proves the
wiring is correct.
"""
from __future__ import annotations

import json

from roundzero.domain.enums import CoverageStatus, InterviewerAction, Phase
from roundzero.domain.interview import ConversationState, TargetRole
from roundzero.evaluation.rubric_loader import rubric_dimension_keys
from roundzero.interviewers.backend_system_design.agent import BackendSystemDesignInterviewer
from roundzero.llm.gateway import LLMGateway

ROUND_TYPE = "backend_system_design"


def _default_coverage() -> dict[str, CoverageStatus]:
    return {dim: CoverageStatus.NOT_COVERED for dim in rubric_dimension_keys(ROUND_TYPE)}


class FakeLLMGateway(LLMGateway):
    """Returns a single canned, valid InterviewerOutput JSON payload."""

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        assert system, "system prompt must not be empty"
        assert "Scenario:" in user_message
        coverage = {k: v.value for k, v in _default_coverage().items()}
        coverage["high_level_architecture"] = CoverageStatus.WEAK.value
        return json.dumps(
            {
                "utterance": "How would this design handle a 10x traffic spike?",
                "action": InterviewerAction.PROBE.value,
                "competency_tags": ["high_level_architecture"],
                "phase": Phase.HIGH_LEVEL_DESIGN.value,
                "coverage": coverage,
            }
        )


def test_first_turn_wires_prompt_scenario_and_agent_together():
    target_role = TargetRole(role_family="backend_engineer", level="staff", domain="")
    interviewer = BackendSystemDesignInterviewer(FakeLLMGateway())

    scenario = interviewer.pick_scenario(target_role)
    assert "prompt" in scenario

    state = ConversationState(time_remaining_sec=60 * 60, coverage=_default_coverage())
    output = interviewer.next_turn(scenario=scenario, state=state, candidate_message=None)

    assert output.action == InterviewerAction.PROBE
    assert output.phase == Phase.HIGH_LEVEL_DESIGN
    assert state.phase == Phase.HIGH_LEVEL_DESIGN
    assert len(state.turns) == 1
    assert state.turns[0].speaker == "interviewer"


def test_hard_time_cutoff_forces_wrap_without_calling_the_model():
    target_role = TargetRole(role_family="backend_engineer", level="staff", domain="")

    class ExplodingGateway(LLMGateway):
        def complete_json(self, *, system, user_message, max_tokens=1024):
            raise AssertionError("model should not be called once time is up")

    interviewer = BackendSystemDesignInterviewer(ExplodingGateway())
    scenario = interviewer.pick_scenario(target_role)
    state = ConversationState(time_remaining_sec=0, coverage=_default_coverage())

    output = interviewer.next_turn(scenario=scenario, state=state, candidate_message="still designing...")

    assert output.action == InterviewerAction.WRAP
    assert output.phase == Phase.WRAP_UP


def test_target_role_is_surfaced_in_the_prompt_when_given():
    target_role = TargetRole(role_family="backend_engineer", level="principal", domain="", company_profile="big_tech")

    seen_messages = []

    class RecordingGateway(LLMGateway):
        def complete_json(self, *, system, user_message, max_tokens=1024):
            seen_messages.append(user_message)
            return json.dumps(
                {
                    "utterance": "Let's dig into your data model.",
                    "action": InterviewerAction.PROBE.value,
                    "competency_tags": [],
                    "phase": Phase.API_DATA_MODEL.value,
                    "coverage": {k: v.value for k, v in _default_coverage().items()},
                }
            )

    interviewer = BackendSystemDesignInterviewer(RecordingGateway())
    scenario = interviewer.pick_scenario(target_role)
    state = ConversationState(time_remaining_sec=60 * 60, coverage=_default_coverage())

    interviewer.next_turn(scenario=scenario, state=state, candidate_message=None, target_role=target_role)
    assert "Candidate's target:" in seen_messages[0]

    interviewer.next_turn(scenario=scenario, state=state, candidate_message="okay")
    assert "Candidate's target:" not in seen_messages[1]


def test_every_scenario_has_a_level_tag_and_prompt():
    interviewer = BackendSystemDesignInterviewer(FakeLLMGateway())
    for level in ("senior", "staff", "principal"):
        target_role = TargetRole(role_family="backend_engineer", level=level, domain="")
        scenario = interviewer.pick_scenario(target_role)
        assert level in scenario["level"]
        assert scenario["prompt"]
