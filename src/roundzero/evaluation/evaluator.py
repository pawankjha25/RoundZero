"""
Evaluator - Milestone 2. Runs post-hoc off a frozen transcript (PRD section 10;
CLAUDE.md decision 4). Scores each rubric dimension with cited evidence and
computes readiness %/hire signal deterministically (plan.md: "must be a
deterministic derived value, not a model output") - nothing else. Primary
concern and improvement plan are deliberately NOT computed here - see
roundzero.debrief.synthesis and roundzero.improvement.plan, and models.py's
docstring for why.

Today this ships as RuleBasedEvaluator, not an LLM-based Evidence
Extractor+Evaluator (PRD section 10 steps 2-3), because there is no real LLM key
wired in yet (MockLLMGateway only) - scoring off an LLM that outputs scripted
generic text would be evaluation theater, not a real signal. RuleBasedEvaluator
scores off the interviewer's own coverage map instead (a legitimate, if coarser,
signal - it already reflects how much of each dimension got surfaced). It is
written behind the same Evaluator interface an LLMEvaluator will implement later,
so swapping in real evidence extraction once AnthropicGateway is live does not
touch callers (apps/api/orchestrator.py).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod

from roundzero.domain.enums import CoverageStatus
from roundzero.evaluation.models import DimensionScore, EvidenceItem, ScoredRound
from roundzero.evaluation.rubric_loader import load_rubric
from roundzero.llm.gateway import LLMGateway
from roundzero.llm.prompt_loader import load_evaluator_prompt

HIRE_SIGNAL_THRESHOLDS = [
    (80, "STRONG HIRE"),
    (65, "HIRE"),
    (50, "LEAN HIRE"),
    (35, "LEAN NO HIRE"),
    (0, "NO HIRE"),
]

_COVERAGE_BASE_SCORE = {
    CoverageStatus.COVERED: 3,
    CoverageStatus.WEAK: 2,
    CoverageStatus.NOT_COVERED: 1,
}


def hire_signal_for(readiness_pct: int) -> str:
    for threshold, label in HIRE_SIGNAL_THRESHOLDS:
        if readiness_pct >= threshold:
            return label
    return "NO HIRE"


def compute_readiness(dimension_scores: list[DimensionScore]) -> tuple[int, str]:
    """Weighted average of anchored 1-4 scores -> 0-100 readiness, then a hire
    signal threshold. Shared by every Evaluator implementation so the "never a
    direct model output" rule (plan.md) can't accidentally be reintroduced by a
    future evaluator that forgets to reimplement it."""
    weighted_sum = sum(d.score * d.weight for d in dimension_scores)
    total_weight = sum(d.weight for d in dimension_scores) or 1.0
    weighted_avg = weighted_sum / total_weight  # 1..4
    readiness_pct = round(max(0.0, min(1.0, (weighted_avg - 1) / 3)) * 100)
    return readiness_pct, hire_signal_for(readiness_pct)


class Evaluator(ABC):
    @abstractmethod
    def evaluate(
        self,
        *,
        round_id: str,
        round_type: str,
        transcript: list[dict],
        final_coverage: dict[str, str],
    ) -> ScoredRound:
        """transcript: ordered list of {speaker, text, phase, competency_tags}.
        final_coverage: dimension -> CoverageStatus value from the last interviewer turn."""
        raise NotImplementedError


class RuleBasedEvaluator(Evaluator):
    def __init__(self, rubric_version: str = "v1"):
        self._rubric_version = rubric_version

    def evaluate(
        self,
        *,
        round_id: str,
        round_type: str,
        transcript: list[dict],
        final_coverage: dict[str, str],
    ) -> ScoredRound:
        rubric = load_rubric(round_type, self._rubric_version)
        dimension_scores = [
            self._score_dimension(dim_cfg, transcript, final_coverage) for dim_cfg in rubric["dimensions"]
        ]

        readiness_pct, hire_signal = compute_readiness(dimension_scores)

        return ScoredRound(
            round_id=round_id,
            dimension_scores=dimension_scores,
            readiness_pct=readiness_pct,
            hire_signal=hire_signal,
        )

    def _score_dimension(self, dim_cfg: dict, transcript: list[dict], final_coverage: dict[str, str]) -> DimensionScore:
        dim = dim_cfg["key"]
        status = CoverageStatus(final_coverage.get(dim, CoverageStatus.NOT_COVERED.value))
        score = _COVERAGE_BASE_SCORE[status]

        evidence = self._collect_evidence(dim, transcript)
        if status == CoverageStatus.COVERED and len(evidence) >= 3:
            score = 4  # probed repeatedly and stayed COVERED - exceeds target bar

        narrative = self._render_narrative(dim_cfg["label"], score, status, evidence)
        return DimensionScore(
            dimension=dim,
            label=dim_cfg["label"],
            weight=dim_cfg["weight"],
            score=score,
            evidence_narrative=narrative,
            evidence=evidence,
        )

    def _collect_evidence(self, dim: str, transcript: list[dict]) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        for i, turn in enumerate(transcript):
            if dim in (turn.get("competency_tags") or []):
                items.append(EvidenceItem(dimension=dim, text=turn["text"], source_turn_index=i))
        return items

    def _render_narrative(self, label: str, score: int, status: CoverageStatus, evidence: list[EvidenceItem]) -> str:
        if not evidence:
            return (
                f"{label} - {score}/4. Not directly probed in this round "
                f"(coverage: {status.value.replace('_', ' ').lower()})."
            )
        quotes = " ".join(f'Interviewer: "{e.text}"' for e in evidence[:2])
        return f"{label} - {score}/4. {quotes} Coverage assessed as {status.value.replace('_', ' ').lower()}."


class LLMEvaluator(Evaluator):
    """GPT-5 mini evaluator (locked V1 stack) - independently scores the frozen
    transcript against the full rubric (anchors and weights included - unlike
    what the interviewer ever sees, PRD section 8's "never expose hidden rubric
    instructions"). Deliberately a different vendor from the Gemini interviewer
    (CLAUDE.md decision 4). Falls back to RuleBasedEvaluator wherever this isn't
    constructed - see apps/api/orchestrator.get_evaluator()."""

    def __init__(self, llm: LLMGateway, rubric_version: str = "v1", prompt_version: str = "v1"):
        self._llm = llm
        self._rubric_version = rubric_version
        self._prompt_version = prompt_version

    def evaluate(
        self,
        *,
        round_id: str,
        round_type: str,
        transcript: list[dict],
        final_coverage: dict[str, str],
    ) -> ScoredRound:
        rubric = load_rubric(round_type, self._rubric_version)
        # Loaded per-call, not cached on self at __init__ time, because a single
        # LLMEvaluator instance (see apps/api/orchestrator.get_evaluator()) is
        # constructed once per process and must be able to score both
        # ml_system_design and coding rounds correctly - see
        # prompts/evaluators/coding/v1.md for the coding-specific persona.
        system_prompt = load_evaluator_prompt(round_type, self._prompt_version)
        user_message = self._build_user_message(rubric, transcript)
        raw = self._llm.complete_json(system=system_prompt, user_message=user_message, max_tokens=2048)
        parsed = json.loads(raw)
        scores_by_dim = {item["dimension"]: item for item in parsed.get("dimension_scores", [])}

        dimension_scores: list[DimensionScore] = []
        for dim_cfg in rubric["dimensions"]:
            dim = dim_cfg["key"]
            item = scores_by_dim.get(dim)
            if item is None:
                score, narrative = 1, "Model did not return a score for this dimension - treated as not addressed."
            else:
                score = max(1, min(4, int(item.get("score", 1))))
                narrative = item.get("evidence_narrative", "")
            dimension_scores.append(
                DimensionScore(
                    dimension=dim,
                    label=dim_cfg["label"],
                    weight=dim_cfg["weight"],
                    score=score,
                    evidence_narrative=narrative,
                    evidence=[],  # LLMEvaluator cites evidence in prose, not atomic EvidenceItems (yet)
                )
            )

        readiness_pct, hire_signal = compute_readiness(dimension_scores)
        return ScoredRound(
            round_id=round_id,
            dimension_scores=dimension_scores,
            readiness_pct=readiness_pct,
            hire_signal=hire_signal,
        )

    def _build_user_message(self, rubric: dict, transcript: list[dict]) -> str:
        scale_text = " | ".join(f"{k}={v}" for k, v in rubric["scale"].items())
        dims_block = "\n".join(
            f"- {d['key']} ({d['label']}, weight {d['weight']})" for d in rubric["dimensions"]
        )
        history = "\n".join(f"{t['speaker']}: {t['text']}" for t in transcript)
        return (
            f"Anchored scale (applies to every dimension): {scale_text}\n\n"
            f"Dimensions to score:\n{dims_block}\n\n"
            f"Full transcript:\n{history}\n\n"
            f"Score every dimension per your instructions and return the required JSON."
        )
