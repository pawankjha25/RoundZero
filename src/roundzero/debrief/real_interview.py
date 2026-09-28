"""
Real Interview Experience structuring - specs/002-full-loop-platform P0.11.
Turns one candidate's freeform account of a real interview into a per-round
breakdown, mirroring debrief/committee.py's exact shape: one LLM call behind
an OPENAI_API_KEY check, a Pydantic output model, and a rule-based fallback
that never fabricates specifics it can't derive from the raw text.

This is a *preview* step only - orchestrator.structure_real_interview_text
never persists this module's output directly. The candidate reviews and
edits the draft before POST /v1/real-interviews actually saves anything (see
apps/api/routes/real_interviews.py's `/structure` endpoint) - same "never
silently commit an LLM output the user hasn't seen" discipline this codebase
already follows elsewhere (e.g. realtime/agent.py's _speak_latest_turn only
ever speaks an already-decided turn, never regenerates one).
"""
from __future__ import annotations

import json

from pydantic import BaseModel

from roundzero.llm.gateway import LLMGateway
from roundzero.llm.prompt_loader import load_real_interview_prompt


class StructuredRound(BaseModel):
    round_type_label: str
    question_family: str
    follow_ups: str = ""
    difficulty: str = ""


class StructuredExperience(BaseModel):
    rounds: list[StructuredRound]
    self_assessment: str = ""


def rule_based_structure_experience(raw_text: str) -> StructuredExperience:
    """No-LLM-key fallback (same "no key required to run the app" rule every
    other LLM feature in this codebase follows). Never invents a per-round
    breakdown it has no way to derive without a model - instead it carries
    the candidate's own raw text forward untouched as a single round entry,
    with an honest note that it wasn't broken down, exactly like
    rule_based_committee_synthesis's own "(Rule-based summary - connect an
    OpenAI key...)" pattern."""
    text = raw_text.strip()
    if not text:
        return StructuredExperience(rounds=[], self_assessment="")
    return StructuredExperience(
        rounds=[
            StructuredRound(
                round_type_label="Not broken down",
                question_family=(
                    "Connect an OpenAI key for an AI-structured per-round breakdown - "
                    "for now, here's what you wrote: " + text
                ),
                follow_ups="",
                difficulty="",
            )
        ],
        self_assessment="",
    )


def llm_structure_experience(
    llm: LLMGateway,
    raw_text: str,
    hints: str = "",
    prompt_version: str = "v1",
) -> StructuredExperience:
    """GPT-5 mini structuring (locked V1 stack, same call shape as
    debrief/committee.py's llm_committee_synthesis). Falls back to
    rule_based_structure_experience on a parse failure or an empty rounds
    list, same "never raise out of a bad LLM response" convention as every
    other synthesis function in this codebase."""
    system_prompt = load_real_interview_prompt(prompt_version)
    user_message = (
        f"Context hints (role/level/domain/company the candidate targeted, if known): {hints or '(none given)'}\n\n"
        f"Candidate's own account of the interview:\n{raw_text}\n\nReturn the required JSON."
    )

    try:
        raw = llm.complete_json(system=system_prompt, user_message=user_message, max_tokens=1536)
        parsed = json.loads(raw)
        rounds = [StructuredRound.model_validate(r) for r in parsed["rounds"]]
        self_assessment = str(parsed.get("self_assessment", ""))
        if not rounds:
            raise ValueError("empty rounds list in structuring response")
    except Exception:
        return rule_based_structure_experience(raw_text)

    return StructuredExperience(rounds=rounds, self_assessment=self_assessment)
