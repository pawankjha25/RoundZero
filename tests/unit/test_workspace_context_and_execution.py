"""
Smoke tests for the Coding + System Design workspace additions (2026-09):
- MLSystemDesignInterviewer.next_turn's new workspace_context param actually
  reaches the LLM prompt (so the interviewer can react to the whiteboard).
- MockCodeExecutionProvider never fabricates a pass/fail verdict.
Same fake-gateway, no-network pattern as test_ml_system_design_agent_smoke.py.
"""
from __future__ import annotations

import json

from roundzero.coding.execution import (
    CodeTestCase,
    MockCodeExecutionProvider,
    PythonSubprocessExecutionProvider,
    get_execution_provider,
)
from roundzero.domain.enums import CoverageStatus, InterviewerAction, Phase
from roundzero.domain.interview import ConversationState, TargetRole, default_coverage
from roundzero.interviewers.ml_system_design.agent import MLSystemDesignInterviewer
from roundzero.llm.gateway import LLMGateway


class RecordingGateway(LLMGateway):
    """Captures the user_message it was called with, so the test can assert
    the workspace context block actually made it into the prompt."""

    def __init__(self):
        self.last_user_message: str | None = None

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        self.last_user_message = user_message
        coverage = {k: v.value for k, v in default_coverage().items()}
        return json.dumps(
            {
                "utterance": "Tell me more about your caching layer.",
                "action": InterviewerAction.PROBE.value,
                "competency_tags": ["architecture"],
                "phase": Phase.HIGH_LEVEL_DESIGN.value,
                "coverage": coverage,
            }
        )


def test_workspace_context_reaches_the_prompt_when_present():
    target_role = TargetRole(role_family="ml_engineer", level="principal", domain="ml_infra")
    gateway = RecordingGateway()
    interviewer = MLSystemDesignInterviewer(gateway)
    scenario = interviewer.pick_scenario(target_role)
    state = ConversationState(time_remaining_sec=45 * 60)

    interviewer.next_turn(
        scenario=scenario,
        state=state,
        candidate_message="Here's my design so far.",
        workspace_context="Components: API Gateway, Redis Cache\nFlow: API Gateway → Redis Cache",
    )

    assert gateway.last_user_message is not None
    assert "Candidate's current whiteboard" in gateway.last_user_message
    assert "Redis Cache" in gateway.last_user_message


def test_workspace_context_omitted_block_when_absent():
    target_role = TargetRole(role_family="ml_engineer", level="principal", domain="ml_infra")
    gateway = RecordingGateway()
    interviewer = MLSystemDesignInterviewer(gateway)
    scenario = interviewer.pick_scenario(target_role)
    state = ConversationState(time_remaining_sec=45 * 60)

    interviewer.next_turn(scenario=scenario, state=state, candidate_message="Hello")

    assert gateway.last_user_message is not None
    assert "Candidate's current whiteboard" not in gateway.last_user_message


def test_mock_code_execution_provider_never_fabricates_a_verdict():
    provider = MockCodeExecutionProvider()
    result = provider.run(
        language="python",
        code="def f(): pass",
        test_cases=[CodeTestCase(name="t1"), CodeTestCase(name="t2")],
    )

    assert result.executed is False
    assert len(result.test_results) == 2
    assert all(tc.passed is None for tc in result.test_results)
    assert "not" in result.stdout.lower()


def test_get_execution_provider_returns_the_real_python_provider():
    assert isinstance(get_execution_provider(), PythonSubprocessExecutionProvider)
