"""
Inverse direction: given what we saw, what caused the outcome? (specs/005)

Deterministic and cheap - recomputed from the persisted evidence events on
every read (CLAUDE.md: state rebuildable from event history). For each
competency:

- path: the believed level after every answer (mean and std), with the node's
  status from that answer's evidence (strong / thin / wrong / none);
- went_wrong_turn: the answer with the largest drop in expected level;
- causes: every negative evidence item (contradicted or absent), ranked by its
  exact leave-one-out impact - replay the belief WITHOUT that item and measure
  how much the final expected level recovers. That is analysis-by-synthesis on
  the same world model the picker uses, not a separate heuristic;
- abstain when the total evidence strength is too low to say anything.
"""
from __future__ import annotations

from roundzero.worldmodel import belief as bl
from roundzero.worldmodel import config
from roundzero.worldmodel.models import Cause, CompetencyDiagnosis, Evidence, PathPoint


def answer_turns(turns: list[dict]) -> list[int]:
    return [t["turn_index"] for t in turns if t["speaker"] == "candidate"]


def question_for(turns: list[dict], answer_turn_index: int) -> str:
    question = ""
    for t in turns:
        if t["turn_index"] >= answer_turn_index:
            break
        if t["speaker"] == "interviewer":
            question = t["text"]
    return question


def probed_dims_for(turns: list[dict], answer_turn_index: int) -> list[str]:
    tags: list[str] = []
    for t in turns:
        if t["turn_index"] >= answer_turn_index:
            break
        if t["speaker"] == "interviewer":
            tags = list(t.get("competency_tags") or [])
    return tags


def node_status(items: list[Evidence]) -> str:
    if not items:
        return "none"
    if any(e.polarity == "contradicted" for e in items):
        return "wrong"
    if any(e.polarity == "demonstrated" and e.strength >= 0.5 for e in items):
        return "strong"
    return "thin"


def _explain(ev: Evidence) -> str:
    if ev.polarity == "contradicted":
        return f"Worked against: {ev.criterion}"
    return f"Not addressed when asked: {ev.criterion}"


def diagnose(
    *,
    round_type: str,
    target_level: str | None,
    turns: list[dict],
    evidence: list[Evidence],
) -> list[CompetencyDiagnosis]:
    comps = config.round_competencies(round_type)
    answers = answer_turns(turns)
    text_by_turn = {t["turn_index"]: t["text"] for t in turns}
    steps = bl.replay(target_level, comps, answers, evidence)
    prior = bl.initial_belief(target_level, comps)
    final = steps[-1][1] if steps else prior

    min_strength = config.diagnosis_setting("min_total_strength")
    min_drop = config.diagnosis_setting("went_wrong_min_drop")
    min_impact = config.diagnosis_setting("min_cause_impact")
    max_causes = int(config.diagnosis_setting("max_causes"))

    results: list[CompetencyDiagnosis] = []
    for comp in comps:
        comp_ev = [e for e in evidence if e.competency == comp]
        total_strength = sum(e.strength for e in comp_ev)

        path: list[PathPoint] = []
        worst_drop, worst_turn = 0.0, None
        prev_mean = prior.expected(comp)
        for i, (turn, b) in enumerate(steps):
            items = [e for e in comp_ev if e.turn_index == turn]
            mean = b.expected(comp)
            drop = mean - prev_mean
            if items and drop < worst_drop:
                worst_drop, worst_turn = drop, turn
            prev_mean = mean
            path.append(
                PathPoint(
                    turn_index=turn,
                    label=f"A{i + 1}",
                    question=question_for(turns, turn),
                    answer=text_by_turn.get(turn, ""),
                    level_mean=round(mean, 4),
                    level_std=round(b.std(comp), 4),
                    status=node_status(items),
                    evidence=items,
                )
            )

        final_mean = final.expected(comp)
        causes: list[Cause] = []
        for idx, ev in enumerate(evidence):
            if ev.competency != comp or ev.polarity == "demonstrated":
                continue
            without = evidence[:idx] + evidence[idx + 1 :]
            recovered = bl.final_belief(target_level, comps, answers, without).expected(comp)
            impact = recovered - final_mean
            if impact >= min_impact:
                causes.append(Cause(turn_index=ev.turn_index, evidence=ev, impact=round(impact, 4),
                                    explanation=_explain(ev)))
        causes.sort(key=lambda c: c.impact, reverse=True)

        abstained = total_strength < min_strength
        mode = final.mode(comp)
        results.append(
            CompetencyDiagnosis(
                competency=comp,
                label=config.competency(comp)["label"],
                final_level=None if abstained else config.level_keys()[mode],
                final_level_label=None if abstained else config.level_label(mode),
                final_mean=round(final_mean, 4),
                confidence=round(final.confidence(comp), 4),
                total_strength=round(total_strength, 4),
                abstained=abstained,
                abstain_reason="Not enough evidence in this round to judge this competency." if abstained else None,
                path=path,
                went_wrong_turn=worst_turn if worst_drop <= -min_drop else None,
                causes=causes[:max_causes],
            )
        )
    return results
