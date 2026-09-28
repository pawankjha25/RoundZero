"""
Technical Leadership interviewer agent - candidate-scoped conversational
situational/behavioral interview about leading technical direction and people
(no canvas, no code - see prompts/interviewers/technical_leadership/v1.md's
"What you can see each turn"). Mirrors roundzero.interviewers.ml_depth.agent.
MLDepthInterviewer's exact structure (same pick_scenario/next_turn shape - see
that module's docstring for the shared design rules this one inherits
unchanged: the interviewer never scores itself, and the server holds the
authoritative time cutoff).

Unlike ml_depth, there is no domain sub-area concept here - scenarios.yaml
doesn't tag a `domain` field, so pick_scenario's matches_domain check is
trivially true for every scenario and this filters on level only. There is
also no workspace_context surfaced in the prompt at all (this round type
always routes to ConversationalWorkspace.tsx, which offers no canvas toggle,
so workspace_context is always None in practice) - kept out of the persona
text entirely rather than describing an "optional whiteboard" that doesn't
exist for this round type, unlike ml_depth's genuinely-optional one.

See prompts/interviewers/technical_leadership/v1.md for the actual
persona/instructions this agent runs against, and
prompts/interviewers/technical_leadership/scenarios.yaml for the seed
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

ROUND_TYPE = "technical_leadership"


class TechnicalLeadershipInterviewer:
    def __init__(self, llm: LLMGateway, prompt_version: str = "v1"):
        self._llm = llm
        self._system_prompt = load_prompt(ROUND_TYPE, prompt_version)
        self._scenarios = load_scenarios(ROUND_TYPE)
        self._rubric_dimensions = rubric_dimension_keys(ROUND_TYPE)

    def pick_scenario(self, target_role: TargetRole, exclude_ids: frozenset[str] = frozenset()) -> dict:
        """Same progressive-relaxation selection as MLSystemDesignInterviewer.
        pick_scenario - see that method's docstring. Filters on level only
        (no domain tags in this round type's scenario bank)."""

        def scenario_id(s: dict) -> str:
            return s.get("id", s.get("name", ""))

        def matches_level(s: dict) -> bool:
            return target_role.level in s.get("level", [])

        def candidates(*, honor_exclude: bool) -> list[dict]:
            return [
                s
                for s in self._scenarios
                if matches_level(s) and (scenario_id(s) not in exclude_ids if honor_exclude else True)
            ]

        pool = candidates(honor_exclude=True) or candidates(honor_exclude=False) or self._scenarios
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

        user_message = self._build_user_message(scenario, state, target_role, voice_mode, focus_hint, probe_hint)
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
            f"{voice_block}\n"
            f"Transcript so far:\n{history}\n\n"
            f"Respond with your next turn as a single JSON object per the output format "
            f"in your instructions."
        )
