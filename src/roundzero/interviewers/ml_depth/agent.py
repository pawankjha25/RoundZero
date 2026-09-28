"""
ML Depth interviewer agent - candidate-scoped conversational deep-dive into one
ML sub-area (LLM/Gen AI, Traditional ML, or Reinforcement Learning). Mirrors
roundzero.interviewers.coding.agent.CodingInterviewer's exact structure (same
pick_scenario/next_turn shape - see that module's docstring for the shared
design rules this one inherits unchanged: the interviewer never scores
itself, and the server holds the authoritative time cutoff).

The only real differences: (1) matches_domain is load-bearing here, not
trivially-true like Coding's - domain (llm_genai / general_ml /
reinforcement_learning) is how the candidate's chosen sub-area actually
selects a scenario, same mechanism ML System Design already used for its own
domain field; (2) _build_user_message describes the candidate's *optional*
whiteboard summary (present only if they opened it and drew something) rather
than a required code/canvas panel, since this round is conversational by
default - see prompts/interviewers/ml_depth/v1.md's "What you can see each
turn" section.

See prompts/interviewers/ml_depth/v1.md for the actual persona/instructions
this agent runs against, and prompts/interviewers/ml_depth/scenarios.yaml for
the seed scenarios (3 per sub-area).
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

ROUND_TYPE = "ml_depth"


class MLDepthInterviewer:
    def __init__(self, llm: LLMGateway, prompt_version: str = "v1"):
        self._llm = llm
        self._system_prompt = load_prompt(ROUND_TYPE, prompt_version)
        self._scenarios = load_scenarios(ROUND_TYPE)
        self._rubric_dimensions = rubric_dimension_keys(ROUND_TYPE)

    def pick_scenario(self, target_role: TargetRole, exclude_ids: frozenset[str] = frozenset()) -> dict:
        """Same progressive-relaxation selection as
        MLSystemDesignInterviewer.pick_scenario - see that method's docstring.
        Here domain is the candidate's chosen sub-area (llm_genai / general_ml /
        reinforcement_learning) - an unrecognized or unset value (the Setup
        page's "All sub-areas" choice sends "") naturally falls through to the
        require_domain=False tier below and draws from every sub-area, without
        needing a special-cased "any" sentinel in this filter itself."""

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

        # Server-authoritative hard cutoff - identical rule to
        # MLSystemDesignInterviewer.next_turn, see that docstring/PRD section 9.
        if state.time_remaining_sec <= 0 and state.phase != Phase.WRAP_UP:
            forced = InterviewerOutput(
                utterance="We're out of time - let's wrap up here. Thanks for talking through this with me.",
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
        # Personalization gap fix (specs/002, 2026-09-03): see
        # MLSystemDesignInterviewer._build_user_message's identical comment.
        target_role_block = f"\nCandidate's target: {target_role.describe()}.\n" if target_role else ""
        focus_block = (
            f"\nFocused practice note: this candidate specifically started this round to "
            f"drill a gap flagged in a prior round - {focus_hint}. Spend extra probing on "
            f"this specific competency across the round; still cover the rest of the round "
            f"normally, don't turn this into a single-topic interrogation.\n"
            if focus_hint
            else ""
        )
        # workspace_context here is RoundWorkspaceState.canvas_summary, exactly
        # like ML System Design - see apps/api/orchestrator._workspace_context
        # (any round_type other than "coding" gets the canvas branch). None
        # until the candidate opens the optional whiteboard toggle and draws
        # something - expected to be the common case for this round type, not
        # a gap, per prompts/interviewers/ml_depth/v1.md's "What you can see
        # each turn" section.
        workspace_block = (
            f"\nCandidate's optional whiteboard (they chose to open it; auto-summarized as "
            f"they draw):\n{workspace_context}\n"
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
