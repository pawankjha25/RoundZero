"""
Improvement Plan - PRD section 13: "prioritized next steps from this round's
evidence." Rule-based: lowest-scoring dimensions first, tie-broken toward higher
rubric weight (a weak but critical dimension matters more than a weak minor one).
"""
from __future__ import annotations

from roundzero.evaluation.models import DimensionScore, ImprovementItem


def build_improvement_plan(dimension_scores: list[DimensionScore], top_n: int = 3) -> list[ImprovementItem]:
    ranked = sorted(dimension_scores, key=lambda d: (d.score, -d.weight))
    return [
        ImprovementItem(
            dimension=d.dimension,
            priority=priority,
            recommendation=_recommendation_for(d),
            based_on=d.evidence_narrative,
        )
        for priority, d in enumerate(ranked[:top_n], start=1)
    ]


def _recommendation_for(dim_score: DimensionScore) -> str:
    if dim_score.score <= 1:
        return f"Build foundational fluency in {dim_score.label.lower()} - this was not addressed at all in the round."
    if dim_score.score == 2:
        return f"Practice going deeper on {dim_score.label.lower()} without being prompted - it surfaced but stayed shallow."
    return f"Keep sharpening {dim_score.label.lower()} - solid, but push toward more sophisticated trade-off reasoning."
