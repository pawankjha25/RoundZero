"""
ML System Design interviewer agent - Milestone 1. See
specs/001-ml-system-design-vertical-slice/plan.md for the phase state machine and
adaptive-probing design, and prompts/interviewers/ml_system_design/v1.md for the
actual persona/instructions this agent runs against.

The interviewer never scores the round - it produces a transcript and a coverage
map that is a *hint* for the (separate, Milestone 2) Evidence Extractor and
Evaluator, never itself the scored evidence. See docs/PRD.md section 10.
"""
from __future__ import annotations

import json
import random

from roundzero.domain.enums import InterviewerAction, Phase
from roundzero.domain.interview import (
    RUBRIC_DIMENSIONS,
    ConversationState,
    ConversationTurn,
    InterviewerOutput,
    TargetRole,
)
from roundzero.llm.gateway import LLMGateway
from roundzero.worldmodel.steering import probe_block
from roundzero.llm.prompt_loader import load_prompt, load_scenarios

ROUND_TYPE = "ml_system_design"


class MLSystemDesignInterviewer:
    def __init__(self, llm: LLMGateway, prompt_version: str = "v1"):
        self._llm = llm
        self._system_prompt = load_prompt(ROUND_TYPE, prompt_version)
        self._scenarios = load_scenarios(ROUND_TYPE)

    def pick_scenario(self, target_role: TargetRole, exclude_ids: frozenset[str] = frozenset()) -> dict:
        """Real selection, now that there are 10+ seeds (tasks.md item 4): filters
        by level AND domain, excludes any scenario id in exclude_ids (the
        candidate's own recently-used scenarios - see orchestrator.create_round,
        which passes their last few round_type attempts so the same problem
        doesn't repeat back-to-back), then picks uniformly at random among what's
        left. Progressively relaxes the filter (level+domain -> level only ->
        ignore exclude_ids -> full list) rather than ever raising, so a thin
        seed set for one level/domain combo still returns something usable."""

        def scenario_id(s: dict) -> str:
            return s.get("id", s.get("name", ""))

        def matches_level(s: dict) -> bool:
            return target_role.level in s.get("level", [])

        def matches_domain(s: dict) -> bool:
            # A scenario with no domain list is treated as domain-agnostic.
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
        # Personalization gap fix (specs/002, 2026-09-03): target_role is
        # optional only for backward-compat call sites (none remain after
        # this pass) - orchestrator.py always passes the real one now, built
        # straight from the RoundAttempt's own stored role/level/domain/
        # company fields. Previously this method never saw it at all, so the
        # model only ever inferred level/domain implicitly from which
        # scenario got handed to it, and company_profile was never surfaced
        # anywhere - the system prompt said "a top-tier technology company"
        # regardless of what was actually chosen at Setup.
        target_role_block = f"\nCandidate's target: {target_role.describe()}.\n" if target_role else ""
        focus_block = (
            f"\nFocused practice note: this candidate specifically started this round to "
            f"drill a gap flagged in a prior round - {focus_hint}. Spend extra probing on "
            f"this specific competency across the round; still cover the rest of the round "
            f"normally, don't turn this into a single-topic interrogation.\n"
            if focus_hint
            else ""
        )
        workspace_block = (
            f"\nCandidate's current whiteboard (auto-summarized as they draw):\n{workspace_context}\n"
            if workspace_context
            else ""
        )
        # Text mode is untouched (voice_mode defaults False) - this only fires
        # for the live voice path (src/roundzero/realtime/agent.py), where a
        # reply written like a chat message takes noticeably longer to speak
        # and to listen to than the same content said out loud the way a real
        # interviewer would say it in conversation.
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
            f"Rubric dimensions (names only): {', '.join(RUBRIC_DIMENSIONS)}\n"
            f"Current phase: {state.phase.value}\n"
            f"Time remaining: {state.time_remaining_sec // 60} minutes\n"
            f"Coverage so far: {coverage_json}\n"
            f"{workspace_block}"
            f"{voice_block}\n"
            f"Transcript so far:\n{history}\n\n"
            f"Respond with your next turn as a single JSON object per the output format "
            f"in your instructions."
        )
