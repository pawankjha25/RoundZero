"""
The world model and its state update (specs/005 plan.md).

Model: P(polarity | level, competency), a 3x4 table (rubrics/competencies/
likelihoods_v1.yaml). One evidence item with strength s multiplies the belief by
L^s - s tempers how much a vague item can move it. Per answer, the total
strength applied to one competency is capped (per_turn_strength_cap) so a long
answer with many items cannot swing the belief on its own, and probabilities are
floored so a belief can always recover.

Everything downstream - the picker's predictions, diagnosis' leave-one-out
causes, flip/retry projections - is the same `replay` over a (possibly edited)
evidence list, which is what makes the three directions one model.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from roundzero.worldmodel import config
from roundzero.worldmodel.models import Belief, Evidence


def initial_belief(target_level: str | None, competencies: Iterable[str]) -> Belief:
    prior = config.prior_for(target_level)
    return Belief(probs={c: list(prior) for c in competencies})


def _normalize(row: list[float], floor: float) -> list[float]:
    total = sum(row)
    if total <= 0:
        row = [1.0] * len(row)
        total = float(len(row))
    row = [max(p / total, floor) for p in row]
    total = sum(row)
    return [p / total for p in row]


def apply_evidence(belief: Belief, items: list[Evidence]) -> Belief:
    """Bayes update for the evidence from ONE answer. Items whose competency is
    None (cross-cutting dimensions like communication) or not tracked in this
    belief are ignored."""
    floor = config.update_setting("floor")
    cap = config.update_setting("per_turn_strength_cap")

    by_comp: dict[str, list[Evidence]] = defaultdict(list)
    for ev in items:
        if ev.competency and ev.competency in belief.probs and ev.strength > 0:
            by_comp[ev.competency].append(ev)

    probs = {c: list(row) for c, row in belief.probs.items()}
    for comp, evs in by_comp.items():
        total_strength = sum(e.strength for e in evs)
        scale = min(1.0, cap / total_strength) if total_strength > 0 else 0.0
        row = probs[comp]
        for ev in evs:
            lik = config.likelihood_row(comp, ev.polarity)
            s = ev.strength * scale
            row = [p * (l ** s) for p, l in zip(row, lik)]
        probs[comp] = _normalize(row, floor)
    return Belief(probs=probs)


def replay(
    target_level: str | None,
    competencies: Iterable[str],
    answer_turns: list[int],
    evidence: list[Evidence],
) -> list[tuple[int, Belief]]:
    """Belief after each answer, in order. `answer_turns` are the candidate
    turn indexes (so answers with no evidence still get a path point)."""
    competencies = list(competencies)
    by_turn: dict[int, list[Evidence]] = defaultdict(list)
    for ev in evidence:
        by_turn[ev.turn_index].append(ev)
    belief = initial_belief(target_level, competencies)
    out: list[tuple[int, Belief]] = []
    for turn in answer_turns:
        belief = apply_evidence(belief, by_turn.get(turn, []))
        out.append((turn, belief))
    return out


def final_belief(
    target_level: str | None,
    competencies: Iterable[str],
    answer_turns: list[int],
    evidence: list[Evidence],
) -> Belief:
    steps = replay(target_level, competencies, answer_turns, evidence)
    if steps:
        return steps[-1][1]
    return initial_belief(target_level, competencies)


def predict_polarity(belief: Belief, competency: str) -> dict[str, float]:
    """Forward prediction: P(polarity) of the next evidence item on this
    competency under the current belief."""
    row = belief.probs[competency]
    return {
        pol: sum(p * l for p, l in zip(row, config.likelihood_row(competency, pol)))
        for pol in config.POLARITIES
    }
