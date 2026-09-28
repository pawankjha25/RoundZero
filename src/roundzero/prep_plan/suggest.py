"""
Prep Plan question suggestion - user-pitched feature (not from the P0
backlog): a candidate's own self-curated prep plan, organized into areas
each holding a list of practice questions they pick from deliberately
("what am I in the mood to practice today") instead of always getting a
randomly picked scenario via pick_scenario(). This module is the "AI
suggest" half of adding a question to an area - see
orchestrator.suggest_prep_plan_questions for the OPENAI_API_KEY branch that
calls into this module, and PrepPlanQuestion's docstring (apps/api/
models.py) for the full source="bank"|"custom"|"ai" picture.

Mirrors debrief/real_interview.py's exact shape: a Pydantic output model, an
LLM path behind an OPENAI_API_KEY check, and a fallback that's used both
when no key is set AND always for Coding areas (never behind a key check for
Coding - see suggest_questions_from_bank's docstring). Unlike
debrief/real_interview.py's rule-based fallback, this one is not a degraded
stub - it surfaces real, curated content from the existing scenario bank
(prompts/interviewers/{round_type}/scenarios.yaml), so it's genuinely useful
rather than just an honest placeholder.

This is a *preview* step only - orchestrator.suggest_prep_plan_questions
never persists these suggestions. The candidate adds whichever ones they
want, individually, from the plan page - same "never silently commit an LLM
output the user hasn't seen" discipline as
debrief/real_interview.py/llm_structure_experience.
"""
from __future__ import annotations

import json

from pydantic import BaseModel

from roundzero.domain.interview import TargetRole
from roundzero.llm.gateway import LLMGateway
from roundzero.llm.prompt_loader import load_prep_plan_prompt, load_scenarios

# Round types whose interviewer runs from a plain prompt string, with no
# structured fields a freeform question would be missing. Coding is
# deliberately excluded - its scenarios carry title/constraints/entry_point/
# starter_code_python/test_cases (orchestrator._SCENARIO_META_KEYS) that a
# generated freeform question has no way to supply, so llm_suggest_questions
# is never called for a Coding area; suggest_questions_from_bank (real,
# runnable bank scenarios) is used unconditionally for Coding instead.
FREEFORM_ROUND_TYPES = frozenset(
    {"ml_system_design", "ml_depth", "backend_system_design", "technical_leadership", "xfn"}
)


class SuggestedQuestion(BaseModel):
    prompt: str
    notes: str = ""
    # Set only by suggest_questions_from_bank, so the caller can add a
    # accepted bank suggestion with source="bank" + this scenario_id
    # (a real, runnable scenario) rather than source="ai" (freeform text) -
    # see orchestrator.suggest_prep_plan_questions.
    scenario_id: str | None = None


def scenario_id_of(s: dict) -> str:
    return s.get("id", s.get("name", ""))


def filter_bank_scenarios(
    round_type: str,
    target_role: TargetRole,
    exclude_scenario_ids: frozenset[str] = frozenset(),
) -> list[dict]:
    """Shared level/domain filter over a round type's real scenario bank -
    same progressive-relax behavior MLSystemDesignInterviewer.pick_scenario
    uses (level+domain -> level only -> ignore already-excluded -> full
    list, never raising, never empty as long as the bank has any scenarios
    for that round type at all). Used both to browse a bank for "add from
    bank" (orchestrator.list_bank_scenarios_for_area, no cap) and as the
    basis for suggest_questions_from_bank below (capped to 5)."""
    scenarios = load_scenarios(round_type)

    def matches_level(s: dict) -> bool:
        return target_role.level in s.get("level", [])

    def matches_domain(s: dict) -> bool:
        return not s.get("domain") or target_role.domain in s.get("domain", [])

    def candidates(*, require_domain: bool, honor_exclude: bool) -> list[dict]:
        return [
            s
            for s in scenarios
            if matches_level(s)
            and (matches_domain(s) if require_domain else True)
            and (scenario_id_of(s) not in exclude_scenario_ids if honor_exclude else True)
        ]

    return (
        candidates(require_domain=True, honor_exclude=True)
        or candidates(require_domain=False, honor_exclude=True)
        or candidates(require_domain=True, honor_exclude=False)
        or candidates(require_domain=False, honor_exclude=False)
        or list(scenarios)
    )


def suggest_questions_from_bank(
    round_type: str,
    target_role: TargetRole,
    existing_scenario_ids: frozenset[str] = frozenset(),
) -> list[SuggestedQuestion]:
    """No-LLM-key fallback, and the ONLY suggestion path ever used for
    Coding areas (regardless of whether a key is set - see
    FREEFORM_ROUND_TYPES). Genuinely useful, curated, runnable content
    rather than an invented placeholder - returns up to 5 bank scenarios not
    already added to this area."""
    pool = filter_bank_scenarios(round_type, target_role, existing_scenario_ids)
    return [
        SuggestedQuestion(prompt=s["prompt"], notes="", scenario_id=scenario_id_of(s))
        for s in pool[:5]
    ]


def llm_suggest_questions(
    llm: LLMGateway,
    round_type: str,
    target_role: TargetRole,
    existing_prompts: list[str],
    prompt_version: str = "v1",
) -> list[SuggestedQuestion]:
    """GPT-5 mini suggestion (locked V1 stack, same call shape as
    debrief/real_interview.py's llm_structure_experience). Only ever called
    for round_type in FREEFORM_ROUND_TYPES - callers are responsible for
    routing Coding to suggest_questions_from_bank instead, not re-checked
    here. Falls back to suggest_questions_from_bank on a parse failure or an
    empty questions list, same "never raise out of a bad LLM response"
    convention as every other suggestion/structuring function here."""
    system_prompt = load_prep_plan_prompt(prompt_version)
    existing_block = "\n".join(f"- {p}" for p in existing_prompts) or "(none yet)"
    user_message = (
        f"Round type: {round_type}\n"
        f"Target: {target_role.describe()}\n\n"
        f"Questions already in this area (do not repeat or lightly reword these):\n{existing_block}\n\n"
        "Return the required JSON."
    )

    try:
        raw = llm.complete_json(system=system_prompt, user_message=user_message, max_tokens=1024)
        parsed = json.loads(raw)
        questions = [SuggestedQuestion.model_validate(q) for q in parsed["questions"]]
        if not questions:
            raise ValueError("empty questions list in suggestion response")
    except Exception:
        return suggest_questions_from_bank(round_type, target_role)

    return questions
