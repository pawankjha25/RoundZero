"""
Virtual Hiring Committee synthesis - specs/002-full-loop-platform P0.6. Combines
every evaluated round in a finished multi-round loop into one cross-round verdict,
the loop-level analog of debrief/synthesis.py's single-round Primary Concern.

Same split as everywhere else in this codebase (evaluator scores deterministically,
LLM only writes prose on top - evaluation/evaluator.py's compute_readiness,
debrief/synthesis.py's llm_report_synthesis): overall_readiness_pct/hire_signal/
confidence are computed here in plain Python from already-persisted per-round
readiness numbers, never asked of the LLM. The LLM call (llm_committee_synthesis)
only ever produces the qualitative fields - headline/strengths/concerns/
level_signal/key_evidence - grounded in the dimension evidence it's given.

Deliberately does NOT produce a calibrated level range (e.g. "Strong Senior ->
Staff") - that's P0.4 (Level Calibration against explicit level-expectation
definitions), which doesn't exist in this repo yet. Inventing a range without
that data would be exactly the "fabricated precision" specs/002's own P0.13 item
warns against. `level_signal` here is a plain, evidence-grounded directional read
instead (see prompts/committee/v1.md's "Level Judge" section).
"""
from __future__ import annotations

import json

from pydantic import BaseModel

from roundzero.evaluation.evaluator import hire_signal_for
from roundzero.evaluation.models import RoundEvaluation
from roundzero.llm.gateway import LLMGateway
from roundzero.llm.prompt_loader import load_committee_prompt

ROUND_TYPE_LABELS = {
    "ml_system_design": "ML System Design",
    "coding": "Coding",
    "ml_depth": "ML Depth",
    "backend_system_design": "Backend System Design",
    "technical_leadership": "Technical Leadership",
    "xfn": "Cross-functional",
}


def _round_label(round_type: str) -> str:
    return ROUND_TYPE_LABELS.get(round_type, round_type.replace("_", " ").title())


class CommitteeReport(BaseModel):
    """Loop-level synthesis output - what GET/POST /v1/loops/{id}/committee return
    (via CommitteeReportOut in apps/api/schemas.py) and what
    apps/api/models.py::LoopCommitteeRecord persists."""

    overall_readiness_pct: int
    overall_hire_signal: str
    confidence: str  # "medium" | "high" - see _confidence_for below
    headline: str
    strengths: list[str]
    concerns: list[str]
    level_signal: str
    key_evidence: list[str]


def _confidence_for(round_count: int) -> str:
    """Deterministic, not LLM-judged - same "never fabricate confidence" spirit
    as everywhere else numeric in this module. Two rounds is the minimum this
    synthesis ever runs on (orchestrator.loop_committee_eligible requires 2+),
    so two is "medium" (real, but still a small sample) and three or more is
    "high"."""
    return "high" if round_count >= 3 else "medium"


def _overall_readiness(evaluations: list[RoundEvaluation]) -> tuple[int, str]:
    pct = round(sum(e.readiness_pct for e in evaluations) / len(evaluations))
    return pct, hire_signal_for(pct)


def rule_based_committee_synthesis(
    rounds: list[tuple[str, RoundEvaluation]],
    target_level: str,
) -> CommitteeReport:
    """No-LLM-key fallback (same "no key required to run the app" rule every
    other LLM feature in this codebase follows - orchestrator.get_gateway/
    get_evaluator's docstrings). Headline/level_signal are plain factual
    sentences built from the numbers; strengths/concerns come from each round's
    own highest/lowest-scoring dimension (already real, already evidence-backed
    - just not synthesized across rounds by an LLM); key_evidence pulls each
    round's own top-weighted dimension's evidence narrative verbatim, never
    invented."""
    evaluations = [ev for _, ev in rounds]
    pct, signal = _overall_readiness(evaluations)
    confidence = _confidence_for(len(rounds))

    headline = (
        f"{signal} across {len(rounds)} rounds - average readiness {pct}%. "
        "(Rule-based summary - connect an OpenAI key for a synthesized committee verdict.)"
    )

    strengths: list[str] = []
    concerns: list[str] = []
    key_evidence: list[str] = []
    for round_type, ev in rounds:
        label = _round_label(round_type)
        if not ev.dimension_scores:
            continue
        best = max(ev.dimension_scores, key=lambda d: (d.score, d.weight))
        worst = min(ev.dimension_scores, key=lambda d: (d.score, -d.weight))
        strengths.append(f"{label}: {best.label} ({best.score}/4)")
        if worst.dimension != best.dimension:
            concerns.append(f"{label}: {worst.label} ({worst.score}/4)")
        top = max(ev.dimension_scores, key=lambda d: d.weight)
        if top.evidence_narrative:
            key_evidence.append(f"{label}: {top.evidence_narrative}")

    level_signal = (
        f"Based on {len(rounds)} evaluated rounds against the stated target level "
        f"({target_level}) - overall readiness {pct}%."
    )

    return CommitteeReport(
        overall_readiness_pct=pct,
        overall_hire_signal=signal,
        confidence=confidence,
        headline=headline,
        strengths=strengths[:4] or [f"Evaluated {len(rounds)} rounds - see individual reports for detail."],
        concerns=concerns[:4] or ["No single weak dimension stood out - performance was even across rounds."],
        level_signal=level_signal,
        key_evidence=key_evidence[:4],
    )


def llm_committee_synthesis(
    llm: LLMGateway,
    rounds: list[tuple[str, RoundEvaluation]],
    target_level: str,
    prompt_version: str = "v1",
) -> CommitteeReport:
    """GPT-5 mini committee synthesis (locked V1 stack, same call shape as
    debrief/synthesis.py's llm_report_synthesis) - one combined call for the
    Advocate/Skeptic/Level Judge framing (prompts/committee/v1.md), never three
    separate LLM calls, per P0.6's own "logical roles inside one orchestration
    workflow" spec language.

    Computes overall_readiness_pct/hire_signal/confidence itself, same as the
    rule-based path - the LLM is never asked for those. Falls back to
    rule_based_committee_synthesis on a malformed/incomplete response, same
    "never raise out of a bad LLM response" convention as llm_report_synthesis's
    own build_improvement_plan fallback."""
    pct, signal = _overall_readiness([ev for _, ev in rounds])
    confidence = _confidence_for(len(rounds))

    system_prompt = load_committee_prompt(prompt_version)
    rounds_block = "\n\n".join(
        f"### {_round_label(round_type)} round (primary concern: {ev.primary_concern})\n"
        + "\n".join(
            f"- {d.dimension} ({d.label}, weight {d.weight}): {d.score}/4 - {d.evidence_narrative}"
            for d in ev.dimension_scores
        )
        for round_type, ev in rounds
    )
    user_message = (
        f"Target level: {target_level}\n\n"
        f"Evaluated rounds in this loop:\n\n{rounds_block}\n\nReturn the required JSON."
    )

    try:
        raw = llm.complete_json(system=system_prompt, user_message=user_message, max_tokens=1536)
        parsed = json.loads(raw)
        headline = parsed["headline"]
        strengths = list(parsed["strengths"])
        concerns = list(parsed["concerns"])
        level_signal = parsed["level_signal"]
        key_evidence = list(parsed.get("key_evidence", []))
        if not headline or not strengths or not concerns or not level_signal:
            raise ValueError("incomplete committee synthesis response")
    except Exception:
        return rule_based_committee_synthesis(rounds, target_level)

    return CommitteeReport(
        overall_readiness_pct=pct,
        overall_hire_signal=signal,
        confidence=confidence,
        headline=headline,
        strengths=strengths,
        concerns=concerns,
        level_signal=level_signal,
        key_evidence=key_evidence,
    )
