"""
Evaluation output contracts - Milestone 2. See docs/PRD.md section 10 (Evaluator),
section 10.1 (readiness/hire signal), Appendix B (EvidenceItem), and
specs/001-ml-system-design-vertical-slice/plan.md ("Evidence extraction format",
"Readiness % - must be a deterministic derived value").

Split deliberately: ScoredRound is the Evaluator's own output (score + evidence
only - plan.md: "keeps the evaluator narrowly 'score with evidence'"). Primary
concern (debrief/synthesis.py) and the improvement plan (improvement/plan.py) are
separate downstream steps composed by apps/api/orchestrator.py into the final
RoundEvaluation the API/UI actually renders.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from roundzero.leveling.calibration import LevelCalibration


class EvidenceItem(BaseModel):
    """Atomic, source-cited observation - PRD Appendix B. The evidence narrative
    rendered per dimension is synthesized from these, never hand-written."""

    dimension: str
    text: str
    source_turn_index: int


class DimensionScore(BaseModel):
    dimension: str
    label: str
    weight: float
    score: int  # anchored 1-4 scale, rubrics/ml_system_design/v1.yaml
    evidence_narrative: str
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ScoredRound(BaseModel):
    """Evaluator output - PRD section 10 "score with evidence," nothing more."""

    round_id: str
    dimension_scores: list[DimensionScore]
    readiness_pct: int
    hire_signal: str  # e.g. "LEAN HIRE" - PRD section 10.1 hire-signal scale


class ImprovementItem(BaseModel):
    dimension: str
    priority: int  # 1 = highest priority
    recommendation: str
    based_on: str  # short pointer back to the evidence that motivated this


class RoundEvaluation(BaseModel):
    """Final composed report - ScoredRound plus the debrief/improvement synthesis
    steps layered on top (apps/api/orchestrator.py). This is what the report API
    and UI render."""

    round_id: str
    dimension_scores: list[DimensionScore]
    readiness_pct: int
    hire_signal: str
    primary_concern: str
    strengths: list[str]
    weaknesses: list[str]
    improvement_plan: list[ImprovementItem]
    # Live-computed from readiness_pct/hire_signal (roundzero.leveling.calibration.
    # calibrate_level), never stored on EvaluationRecord - see that module's
    # docstring for why this is safe to compute from the existing scale rather
    # than a new per-level assessment.
    level_calibration: LevelCalibration
