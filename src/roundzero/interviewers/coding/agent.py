"""
Coding interviewer agent - specs/004-coding-round-type. Mirrors
roundzero.interviewers.ml_system_design.agent.MLSystemDesignInterviewer's
exact structure (same pick_scenario/next_turn shape - see that module's
docstring for the shared design rules this one inherits unchanged: the
interviewer never scores itself, and the server holds the authoritative
time cutoff). The only real differences are: (1) the rubric dimension list
comes from rubrics/coding/v1.yaml via rubric_dimension_keys() instead of the
ml_system_design-specific RUBRIC_DIMENSIONS global, so this file can never
drift out of sync with its own rubric the way a second hardcoded copy of
that list could; (2) _build_user_message describes the candidate's code
editor state (language + current code, from RoundWorkspaceState) instead of
a whiteboard/canvas summary, since Coding has no diagram to render.

See prompts/interviewers/coding/v1.md for the actual persona/instructions
this agent runs against, and prompts/interviewers/coding/scenarios.yaml for
the 10 seed problems.
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

ROUND_TYPE = "coding"


class CodingInterviewer:
    def __init__(self, llm: LLMGateway, prompt_version: str = "v1"):
        self._llm = llm
        self._system_prompt = load_prompt(ROUND_TYPE, prompt_version)
        self._scenarios = load_scenarios(ROUND_TYPE)
        self._rubric_dimensions = rubric_dimension_keys(ROUND_TYPE)

    def pick_scenario(self, target_role: TargetRole, exclude_ids: frozenset[str] = frozenset()) -> dict:
        """Same progressive-relaxation selection as
        MLSystemDesignInterviewer.pick_scenario - see that method's docstring.
        Coding's seed scenarios (prompts/interviewers/coding/scenarios.yaml)
        carry no `domain` key at all (algorithms/data-structures problems
        aren't ML-domain-specific), so matches_domain is trivially true for
        all of them and this mainly filters by level."""

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
        test_result_context: str | None = None,
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
                utterance="We're out of time - let's stop here. Thanks for working through the problem with me.",
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
            scenario, state, target_role, workspace_context, voice_mode, test_result_context, focus_hint, probe_hint
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
        test_result_context: str | None = None,
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
        # workspace_context here is RoundWorkspaceState.code_text (see
        # apps/api/orchestrator._workspace_context) - the candidate's current
        # code, not a summary of it. Real Run-button results are a separate
        # block below (test_result_context) - kept apart from the code itself
        # so the model can't confuse "what's in the editor right now" with
        # "what actually ran a moment ago", which may already be stale if the
        # candidate edited since their last Run.
        workspace_block = (
            f"\nCandidate's current code (editor buffer, may be mid-edit/incomplete):\n"
            f"```\n{workspace_context}\n```\n"
            if workspace_context
            else "\nCandidate hasn't written any code yet.\n"
        )
        # Real Run-button results (apps.api.orchestrator._latest_coding_test_result),
        # not the editor buffer above - only present once the candidate has
        # actually clicked Run at least once. Lets Ava react to a real pass/fail
        # the way a real interviewer watching your screen would, instead of only
        # ever seeing the code as text and never learning whether it works.
        test_result_block = f"\n{test_result_context}\n" if test_result_context else ""
        voice_block = (
            "\nThis is a live spoken voice conversation, not a text chat - the candidate "
            "hears your utterance read aloud. Keep it brief and conversational (roughly "
            "1-3 short sentences), the way a real interviewer would actually speak, not "
            "write. Ask one clear question or make one clear point at a time.\n"
            if voice_mode
            else ""
        )
        return (
            f"Problem: {scenario['prompt']}\n"
            f"{target_role_block}"
            f"{focus_block}{probe_block(probe_hint)}\n"
            f"Constraints: {scenario.get('constraints', '(none stated)')}\n"
            f"Entry point function: {scenario.get('entry_point', '(unspecified)')}\n\n"
            f"Rubric dimensions (names only): {', '.join(self._rubric_dimensions)}\n"
            f"Current phase: {state.phase.value}\n"
            f"Time remaining: {state.time_remaining_sec // 60} minutes\n"
            f"Coverage so far: {coverage_json}\n"
            f"{workspace_block}"
            f"{test_result_block}"
            f"{voice_block}\n"
            f"Transcript so far:\n{history}\n\n"
            f"Respond with your next turn as a single JSON object per the output format "
            f"in your instructions."
        )
