"""
Gate 3 tooling (specs/005): export transitions, fit the world model from data,
and compare it with the hand-set v1 table on held-out rounds.

A transition is one evidence item on a competency in a round whose level on
that competency was reviewed by Pawan: (round_id, competency, level_index,
polarity). The v1 world model predicts P(polarity | level); the fitted one is
the same shape, estimated from counts with Laplace smoothing. The fitted table
only replaces v1 if it has lower held-out log loss AND the split is by round
(never by item - items from one round must not sit in both train and test).

This is deliberately the smallest learned upgrade that can be honestly tested
with the data volumes a pilot produces. An action-conditioned sequence model
(the design doc's later upgrade) plugs in behind the same comparison once
there are thousands of follow-up -> response transitions.
"""
from __future__ import annotations

import random
from collections import defaultdict

from roundzero.worldmodel import config
from roundzero.worldmodel.metrics import mean_log_loss

Transition = tuple[str, str, int, str]  # (round_id, competency, level_index, polarity)


def fit_likelihoods(transitions: list[Transition], alpha: float = 1.0, min_per_competency: int = 30) -> dict:
    """Returns {"default": table, "overrides": {competency: table}} in the same
    shape as rubrics/competencies/likelihoods_v1.yaml."""
    n_levels = len(config.level_keys())

    def table_from(rows: list[Transition]) -> dict:
        counts = {pol: [alpha] * n_levels for pol in config.POLARITIES}
        for _, _, lvl, pol in rows:
            counts[pol][lvl] += 1
        totals = [sum(counts[pol][i] for pol in config.POLARITIES) for i in range(n_levels)]
        return {pol: [round(counts[pol][i] / totals[i], 4) for i in range(n_levels)] for pol in config.POLARITIES}

    by_comp: dict[str, list[Transition]] = defaultdict(list)
    for t in transitions:
        by_comp[t[1]].append(t)
    return {
        "default": table_from(transitions),
        "overrides": {c: table_from(rows) for c, rows in by_comp.items() if len(rows) >= min_per_competency},
    }


def _prob(table: dict, competency: str, level: int, polarity: str) -> float:
    t = (table.get("overrides") or {}).get(competency) or table["default"]
    return t[polarity][level]


def v1_table() -> dict:
    data = config.load_likelihoods()
    return {"default": data["default"], "overrides": data.get("overrides") or {}}


def split_by_round(transitions: list[Transition], test_share: float = 0.3, seed: int = 0) -> tuple[list, list]:
    rounds = sorted({t[0] for t in transitions})
    rng = random.Random(seed)
    rng.shuffle(rounds)
    n_test = max(1, round(len(rounds) * test_share)) if rounds else 0
    test_rounds = set(rounds[:n_test])
    return ([t for t in transitions if t[0] not in test_rounds], [t for t in transitions if t[0] in test_rounds])


def compare_on_heldout(transitions: list[Transition], seed: int = 0) -> dict:
    train, test = split_by_round(transitions, seed=seed)
    fitted = fit_likelihoods(train)
    base = v1_table()
    ll_v1 = mean_log_loss([_prob(base, c, lvl, pol) for _, c, lvl, pol in test])
    ll_fit = mean_log_loss([_prob(fitted, c, lvl, pol) for _, c, lvl, pol in test])
    return {
        "train_transitions": len(train),
        "test_transitions": len(test),
        "log_loss_v1_table": round(ll_v1, 4),
        "log_loss_fitted": round(ll_fit, 4),
        "fitted_wins": ll_fit < ll_v1,
        "fitted_table": fitted,
    }
