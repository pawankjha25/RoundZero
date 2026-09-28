"""
Primary Concern synthesis - plan.md: "a single-round, single-headline version of
what full cross-round Debrief synthesis will later do (PRD section 11)." Kept out
of the Evaluator on purpose (plan.md) so the evaluator stays narrowly "score with
evidence." Rule-based for now (see plan.md open questions - LLM-based synthesis is
an option once a real key is wired in); the interface takes DimensionScores only,
so swapping the implementation later doesn't touch callers.
"""
from __future__ import annotations

import json

from roundzero.evaluation.models import DimensionScore, ImprovementItem
from roundzero.llm.gateway import LLMGateway
from roundzero.llm.prompt_loader import load_report_prompt


def primary_concern(dimension_scores: list[DimensionScore]) -> str:
    best = max(dimension_scores, key=lambda d: (d.score, d.weight))
    worst = min(dimension_scores, key=lambda d: (d.score, -d.weight))
    if best.dimension == worst.dimension:
        return f"Even performance across dimensions - {best.label.lower()} at {best.score}/4 throughout."
    return (
        f"Strongest in {best.label.lower()} ({best.score}/4), but {worst.label.lower()} "
        f"is currently below target-level expectations ({worst.score}/4)."
    )


def strengths_and_weaknesses(dimension_scores: list[DimensionScore], n: int = 2) -> tuple[list[str], list[str]]:
    strong = sorted([d for d in dimension_scores if d.score >= 3], key=lambda d: (d.score * d.weight), reverse=True)
    weak = sorted([d for d in dimension_scores if d.score <= 2], key=lambda d: (d.score, -d.weight))
    return (
        [f"{d.label} ({d.score}/4)" for d in strong[:n]],
        [f"{d.label} ({d.score}/4)" for d in weak[:n]],
    )


def llm_report_synthesis(
    llm: LLMGateway,
    dimension_scores: list[DimensionScore],
    round_type: str = "ml_system_design",
    prompt_version: str = "v1",
) -> tuple[str, list[ImprovementItem]]:
    """GPT-5 mini report synthesis (locked V1 stack) - one combined call for
    primary_concern + improvement_plan rather than two separate LLM calls, since
    they're both "turn scored evidence into candidate-facing prose" and splitting
    them would double the cost for no real quality gain. Still kept out of
    evaluation/evaluator.py (plan.md: the evaluator stays narrowly "score with
    evidence") - this runs as its own step, after evaluation, given only the
    dimension scores/evidence, never the raw transcript or a readiness number."""
    system_prompt = load_report_prompt(round_type, prompt_version)
    dims_block = "\n".join(
        f"- {d.dimension} ({d.label}, weight {d.weight}): {d.score}/4 - {d.evidence_narrative}"
        for d in dimension_scores
    )
    raw = llm.complete_json(
        system=system_prompt,
        user_message=f"Scored dimensions:\n{dims_block}\n\nReturn the required JSON.",
        max_tokens=1536,  # bumped 2026-09 alongside reasoning_effort="low" - see openai_provider.py
    )
    parsed = json.loads(raw)
    concern = parsed.get("primary_concern") or primary_concern(dimension_scores)
    plan_items = [
        ImprovementItem(
            dimension=item["dimension"],
            priority=i + 1,
            recommendation=item.get("recommendation", ""),
            based_on=item.get("based_on", ""),
        )
        for i, item in enumerate(parsed.get("improvement_plan", []))
    ]
    if not plan_items:
        from roundzero.improvement.plan import build_improvement_plan

        plan_items = build_improvement_plan(dimension_scores)
    return concern, plan_items
