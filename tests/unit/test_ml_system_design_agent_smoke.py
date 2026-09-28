"""
Smoke test for the interviewer agent plumbing - domain contracts, prompt/scenario
loader, and agent turn logic - using a fake LLM gateway so it runs with no API key
and no network. Does not judge interview *quality* (that needs the CLI harness and
a real model); it only proves the wiring is correct.
"""
from __future__ import annotations

import json

from roundzero.domain.enums import CoverageStatus, InterviewerAction, Phase
from roundzero.domain.interview import ConversationState, TargetRole, default_coverage
from roundzero.interviewers.ml_system_design.agent import MLSystemDesignInterviewer
from roundzero.llm.gateway import LLMGateway


class FakeLLMGateway(LLMGateway):
    """Returns a single canned, valid InterviewerOutput JSON payload."""

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        assert system, "system prompt must not be empty"
        assert "Scenario:" in user_message
        coverage = {k: v.value for k, v in default_coverage().items()}
        coverage["architecture"] = CoverageStatus.WEAK.value
        return json.dumps(
            {
                "utterance": "How would you prevent one tenant from monopolizing GPU capacity?",
                "action": InterviewerAction.PROBE.value,
                "competency_tags": ["architecture"],
                "phase": Phase.HIGH_LEVEL_DESIGN.value,
                "coverage": coverage,
            }
        )


def test_first_turn_wires_prompt_scenario_and_agent_together():
    target_role = TargetRole(role_family="ml_engineer", level="principal", domain="ml_infra")
    interviewer = MLSystemDesignInterviewer(FakeLLMGateway())

    scenario = interviewer.pick_scenario(target_role)
    assert "prompt" in scenario

    state = ConversationState(time_remaining_sec=45 * 60)
    output = interviewer.next_turn(scenario=scenario, state=state, candidate_message=None)

    assert output.action == InterviewerAction.PROBE
    assert output.phase == Phase.HIGH_LEVEL_DESIGN
    assert state.phase == Phase.HIGH_LEVEL_DESIGN
    assert len(state.turns) == 1
    assert state.turns[0].speaker == "interviewer"


def test_hard_time_cutoff_forces_wrap_without_calling_the_model():
    target_role = TargetRole(role_family="ml_engineer", level="principal", domain="ml_infra")

    class ExplodingGateway(LLMGateway):
        def complete_json(self, *, system, user_message, max_tokens=1024):
            raise AssertionError("model should not be called once time is up")

    interviewer = MLSystemDesignInterviewer(ExplodingGateway())
    scenario = interviewer.pick_scenario(target_role)
    state = ConversationState(time_remaining_sec=0)

    output = interviewer.next_turn(scenario=scenario, state=state, candidate_message="still designing...")

    assert output.action == InterviewerAction.WRAP
    assert output.phase == Phase.WRAP_UP


def test_target_role_is_surfaced_in_the_prompt_when_given():
    # Personalization gap fix (specs/002, 2026-09-03): target_role used to be
    # constructed only for pick_scenario() and never reached the model's live
    # prompt at all. Asserts describe()'s output actually lands in the
    # user_message the FakeLLMGateway receives - and that omitting
    # target_role (the pre-existing default-None call sites, e.g. this file's
    # other tests) still works exactly as before.
    target_role = TargetRole(
        role_family="ml_infra_engineer", level="staff", domain="ml_infra", company_profile="big_tech"
    )

    seen_messages = []

    class RecordingGateway(LLMGateway):
        def complete_json(self, *, system, user_message, max_tokens=1024):
            seen_messages.append(user_message)
            coverage = {k: v.value for k, v in default_coverage().items()}
            return json.dumps(
                {
                    "utterance": "Let's dig into the sharding strategy.",
                    "action": InterviewerAction.PROBE.value,
                    "competency_tags": [],
                    "phase": Phase.HIGH_LEVEL_DESIGN.value,
                    "coverage": coverage,
                }
            )

    interviewer = MLSystemDesignInterviewer(RecordingGateway())
    scenario = interviewer.pick_scenario(target_role)
    state = ConversationState(time_remaining_sec=45 * 60)

    interviewer.next_turn(scenario=scenario, state=state, candidate_message=None, target_role=target_role)
    assert "Candidate's target: Staff ML Infra Engineer role, ML Infra domain, targeting a Big Tech company." in seen_messages[0]

    # No target_role passed -> no such line at all, not a blank/placeholder one.
    interviewer.next_turn(scenario=scenario, state=state, candidate_message="okay")
    assert "Candidate's target:" not in seen_messages[1]
