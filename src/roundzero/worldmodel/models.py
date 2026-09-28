"""
Contracts for the world-model interviewer (specs/005). Pydantic, like the rest
of roundzero's domain contracts - these are also the API response shapes
(apps/api/routes/world_model.py), so field names are what the web client sees.
"""
from __future__ import annotations

import math
from typing import Literal, Optional

from pydantic import BaseModel, Field

Polarity = Literal["demonstrated", "absent", "contradicted"]
NodeStatus = Literal["strong", "thin", "wrong", "none"]


class Evidence(BaseModel):
    """One atomic observation from one candidate answer. `span` is a verbatim
    substring of the answer (None for `absent`) - the unsupported-claim guard
    in extractor.py drops anything else."""

    turn_index: int
    dimension: str
    competency: Optional[str] = None
    criterion: str
    polarity: Polarity
    span: Optional[str] = None
    strength: float = Field(ge=0.0, le=1.0)
    extractor_version: str = ""


class Belief(BaseModel):
    """competency -> probability over levels (rubrics/competencies/v1.yaml order)."""

    probs: dict[str, list[float]]

    def expected(self, competency: str) -> float:
        return sum(i * p for i, p in enumerate(self.probs[competency]))

    def std(self, competency: str) -> float:
        mean = self.expected(competency)
        var = sum(p * (i - mean) ** 2 for i, p in enumerate(self.probs[competency]))
        return math.sqrt(max(var, 0.0))

    def entropy(self, competency: str) -> float:
        return -sum(p * math.log2(p) for p in self.probs[competency] if p > 0)

    def mode(self, competency: str) -> int:
        row = self.probs[competency]
        return max(range(len(row)), key=lambda i: row[i])

    def confidence(self, competency: str) -> float:
        return max(self.probs[competency])


class FollowUpOption(BaseModel):
    competency: str
    label: str
    intent: str
    eig: float
    predicted: dict[str, float]  # polarity -> predicted probability
    blocked_reason: Optional[str] = None


class Decision(BaseModel):
    after_turn_index: int
    mode: str  # off | shadow | live
    options: list[FollowUpOption]
    chosen: Optional[FollowUpOption] = None
    reason: str


class PathPoint(BaseModel):
    turn_index: int
    label: str  # "A1", "A2", ...
    question: str
    answer: str
    level_mean: float  # 0..3 expected level after this answer
    level_std: float
    status: NodeStatus
    evidence: list[Evidence] = Field(default_factory=list)


class Cause(BaseModel):
    turn_index: int
    evidence: Evidence
    impact: float  # recovered expected level if this item were removed (0..3 scale)
    explanation: str


class CompetencyDiagnosis(BaseModel):
    competency: str
    label: str
    final_level: Optional[str] = None  # level key, None when abstained
    final_level_label: Optional[str] = None
    final_mean: float
    confidence: float
    total_strength: float
    abstained: bool = False
    abstain_reason: Optional[str] = None
    path: list[PathPoint] = Field(default_factory=list)
    went_wrong_turn: Optional[int] = None
    causes: list[Cause] = Field(default_factory=list)


class FlipRewrite(BaseModel):
    """Counterfactual - HYPOTHETICAL. Never a training label (spec 005)."""

    id: Optional[str] = None
    competency: str
    turn_index: int
    criterion: str
    polarity: Polarity
    added_text: str
    edited_answer: str
    current_mean: float
    current_level: str
    projected_mean: float
    projected_level: str
    flipped: bool
    rescore_evidence: list[Evidence] = Field(default_factory=list)
    writer_version: str
    scorer_version: str
    hypothetical: bool = True


class RetryResult(BaseModel):
    """Counterfactual - REAL. The only true paired-intervention data Round Zero gets."""

    id: Optional[str] = None
    turn_index: int
    retry_text: str
    evidence: list[Evidence] = Field(default_factory=list)
    before: dict[str, float]  # competency -> final expected level before
    after: dict[str, float]  # competency -> final expected level with the retry swapped in
    scorer_version: str


class WorldModelReport(BaseModel):
    round_id: str
    round_type: str
    target_level: str
    adaptive_mode: str
    extractor_version: Optional[str] = None
    answers_processed: int
    answers_total: int
    competencies: list[CompetencyDiagnosis]
    rewrites: list[FlipRewrite] = Field(default_factory=list)
    retries: list[RetryResult] = Field(default_factory=list)
    flip_available: bool = False
    decisions_logged: int = 0
