"""
Counterfactual direction, REAL: "Retry this answer" (specs/005).

The candidate re-answers one question from the report. The retry is scored by
the same blind extractor, and the belief is replayed with only that answer
swapped - so before/after is a real paired intervention on the same person and
the same question, the only true counterfactual data Round Zero ever gets.
"""
from __future__ import annotations

from roundzero.worldmodel import belief as bl
from roundzero.worldmodel import config
from roundzero.worldmodel.diagnosis import answer_turns, probed_dims_for, question_for
from roundzero.worldmodel.extractor import Extractor
from roundzero.worldmodel.flip import project
from roundzero.worldmodel.models import Evidence, RetryResult


class NotAnAnswerTurnError(ValueError):
    pass


def score_retry(
    *,
    round_type: str,
    target_level: str | None,
    turns: list[dict],
    evidence: list[Evidence],
    turn_index: int,
    retry_text: str,
    scorer: Extractor,
) -> RetryResult:
    answers = answer_turns(turns)
    if turn_index not in answers:
        raise NotAnAnswerTurnError(f"turn {turn_index} is not a candidate answer in this round")
    comps = config.round_competencies(round_type)
    before_belief = bl.final_belief(target_level, comps, answers, evidence)
    new_evidence = scorer.extract(
        round_type=round_type,
        question=question_for(turns, turn_index),
        answer=retry_text,
        turn_index=turn_index,
        probed_dims=probed_dims_for(turns, turn_index),
    )
    after, _ = project(round_type=round_type, target_level=target_level, turns=turns,
                       evidence=evidence, turn_index=turn_index, replacement=new_evidence)
    return RetryResult(
        turn_index=turn_index,
        retry_text=retry_text,
        evidence=new_evidence,
        before={c: round(before_belief.expected(c), 4) for c in comps},
        after=after,
        scorer_version=scorer.version,
    )
