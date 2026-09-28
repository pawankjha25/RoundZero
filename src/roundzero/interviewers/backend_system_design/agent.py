"""
Backend System Design interviewer agent - a classic distributed-systems design
round (URL shortener, rate limiter, chat system, etc.), no ML component. Mirrors
roundzero.interviewers.ml_system_design.agent.MLSystemDesignInterviewer's exact
structure (same pick_scenario/next_turn shape, same server-authoritative time
cutoff, same "never scores itself" rule) - the two round types are the same
"design a production system end-to-end, with a shared canvas" shape, just a
different domain and rubric.

Unlike MLSystemDesignInterviewer (which still imports the legacy hardcoded
RUBRIC_DIMENSIONS global from roundzero.domain.interview), this agent uses
rubric_dimension_keys(ROUND_TYPE) - the same round-type-generic helper
roundzero.interviewers.ml_depth.agent already uses - so its rubric dimensions
can never drift from rubrics/backend_system_design/v1.yaml.

There is no domain sub-filtering here (unlike ml_depth's sub-area mechanism) -
scenarios.yaml doesn't tag a `domain` field, so pick_scenario's matches_domain
check is trivially true for every scenario, same as Coding's.

See prompts/interviewers/backend_system_design/v1.md for the actual
persona/instructions this agent runs against, and
prompts/interviewers/backend_system_design/scenarios.yaml for the seed
scenarios.
"""
from __future__ import annotations

import json
import random

from roundzero.domain.enums import InterviewerAction, Phase
from roundzero.domain.interview import (
    ConversationState,
    ConversationTurn,
    InterviewerOutput,
    TargetRole,
)
from roundzero.evaluation.rubric_loader import rubric_dimension_keys
from roundzero.llm.gateway import LLMGateway
from roundzero.worldmodel.steering import probe_block
from roundzero.llm.prompt_loader import load_prompt, load_scenarios

ROUND_TYPE = "backend_system_design"


class BackendSystemDesignInterviewer:
    def __init__(self, llm: LLMGateway, prompt_version: str = "v1"):
        self._llm = llm
        self._system_prompt = load_prompt(ROUND_TYPE, prompt_version)
        self._scenarios = load_scenarios(ROUND_TYPE)
        self._rubric_dimensions = rubric_dimension_keys(ROUND_TYPE)

    def pick_scenario(self, target_role: TargetRole, exclude_ids: frozenset[str] = frozenset()) -> dict:
        """Same progressive-relaxation selection as MLSystemDesignInterviewer.
        pick_scenario - see that method's docstring. domain is never used to
        filter here (no scenario tags one), so matches_domain is trivially
        true and every relax tier collapses to level + exclude_ids only."""

        def scenario_id(s: dict) -> str:
            return s.get("id", s.get("name", ""))

        def matches_level(s: dict) -> bool:
            return target_role.level in s.get("level", [])

        def matches_domain(s: dict) -> bool:
            return not s.get("domain") or target_role.domain in s.get("domain", [])

        def candidates(*, require_domain: bool, honor_exclude: bool) -> list[dict]:
            return [
                s
                for s in self._scenarios
                if matches_level(s)
                and (matches_domain(s) if require_domain else True)
                and (scenario_id(s) not in exclude_ids if honor_exclude else True)
            ]

        pool = (
            candidates(require_domain=True, honor_exclude=True)
            or candidates(require_domain=False, honor_exclude=True)
            or candidates(require_domain=True, honor_exclude=False)
            or candidates(require_domain=False, honor_exclude=False)
            or self._scenarios
        )
        return random.choice(pool)

    def next_turn(
        self,
        *,
        scenario: dict,
        state: ConversationState,
        candidate_message: str | None,
        target_role: TargetRole | None = None,
        workspace_context: str | None = None,
        voice_mode: bool = False,
        focus_hint: str | None = None,
        probe_hint: str | None = None,
    ) -> InterviewerOutput:
        if candidate_message is not None:
            state.turns.append(
                ConversationTurn(speaker="candidate", text=candidate_message, phase=state.phase)
            )

        # Server-authoritative hard cutoff regardless of what the model would do -
        # PRD section 9: "server is authoritative for round state and timing."
        if state.time_remaining_sec <= 0 and state.phase != Phase.WRAP_UP:
            forced = InterviewerOutput(
                utterance="We're out of time - let's wrap up here. Thanks for walking me through your design.",
                action=InterviewerAction.WRAP,
                competency_tags=[],
                phase=Phase.WRAP_UP,
                coverage=state.coverage,
            )
            state.turns.append(
                ConversationTurn(speaker="interviewer", text=forced.utterance, phase=Phase.WRAP_UP)
            )
            state.phase = Phase.WRAP_UP
            return forced

        user_message = self._build_user_message(
            scenario, state, target_role, workspace_context, voice_mode, focus_hint, probe_hint
        )
        raw = self._llm.complete_json(system=self._system_prompt, user_message=user_message)
        output = InterviewerOutput.model_validate(json.loads(raw))

        state.turns.append(
            ConversationTurn(speaker="interviewer", text=output.utterance, phase=output.phase)
        )
        state.phase = output.phase
        state.coverage = output.coverage
        return output

    def _build_user_message(
        self,
        scenario: dict,
        state: ConversationState,
        target_role: TargetRole | None = None,
        workspace_context: str | None = None,
        voice_mode: bool = False,
        focus_hint: str | None = None,
        probe_hint: str | None = None,
    ) -> str:
        coverage_json = json.dumps({k: v.value for k, v in state.coverage.items()})
        history = "\n".join(f"{t.speaker}: {t.text}" for t in state.turns) or "(interview has not started yet)"
        target_role_block = f"\nCandidate's target: {target_role.describe()}.\n" if target_role else ""
        focus_block = (
            f"\nFocused practice note: this candidate specifically started this round to "
            f"drill a gap flagged in a prior round - {focus_hint}. Spend extra probing on "
            f"this specific competency across the round; still cover the rest of the round "
            f"normally, don't turn this into a single-topic interrogation.\n"
            if focus_hint
            else ""
        )
        # workspace_context here is RoundWorkspaceState.canvas_summary (see
        # apps/api/orchestrator._workspace_context - any round_type other than
        # "coding" gets the canvas branch, and WorkspaceRouter.tsx already
        # routes this round type to the same SystemDesignWorkspace ml_system_
        # design uses). Same "current whiteboard" framing as
        # MLSystemDesignInterviewer's own _build_user_message, not ml_depth's
        # "optional" framing - a canvas is the expected default here.
        workspace_block = (
            f"\nCandidate's current whiteboard (auto-summarized as they draw):\n{workspace_context}\n"
            if workspace_context
            else ""
        )
        voice_block = (
            "\nThis is a live spoken voice conversation, not a text chat - the candidate "
            "hears your utterance read aloud. Keep it brief and conversational (roughly "
            "1-3 short sentences), the way a real interviewer would actually speak, not "
            "write. Ask one clear question or make one clear point at a time.\n"
            if voice_mode
            else ""
        )
        return (
            f"Scenario: {scenario['prompt']}\n"
            f"{target_role_block}"
            f"{focus_block}{probe_block(probe_hint)}\n"
            f"Rubric dimensions (names only): {', '.join(self._rubric_dimensions)}\n"
            f"Current phase: {state.phase.value}\n"
            f"Time remaining: {state.time_remaining_sec // 60} minutes\n"
            f"Coverage so far: {coverage_json}\n"
            f"{workspace_block}"
            f"{voice_block}\n"
            f"Transcript so far:\n{history}\n\n"
            f"Respond with your next turn as a single JSON object per the output format "
            f"in your instructions."
        )
