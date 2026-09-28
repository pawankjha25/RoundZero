"""
Forward direction: Propose -> Predict -> Evaluate -> Decide (specs/005).

Propose: every competency this round type can produce evidence for.
Predict: P(polarity) of a probe on it, from the world model (belief.py).
Evaluate: expected information gain,
    EIG = H(b) - sum_o P(o) H(b | o),
with the probe's likely strength (update.predicted_probe_strength).
Decide: highest EIG after constraints - no competency probed more than twice
in a row, and no steering in the last 2 minutes (the interviewer should be
wrapping up). Pure math, no model call, so it adds no latency.

Mode (config.adaptive_mode): `shadow` logs the decision without steering (the
default until Gate 2); `live` turns the chosen option into a probe hint
(steering.py); `off` skips the picker entirely.
"""
from __future__ import annotations

import math

from roundzero.worldmodel import config
from roundzero.worldmodel.belief import predict_polarity
from roundzero.worldmodel.models import Belief, Decision, FollowUpOption

MAX_CONSECUTIVE_PROBES = 2
NO_STEER_LAST_SEC = 120


def _entropy(row: list[float]) -> float:
    return -sum(p * math.log2(p) for p in row if p > 0)


def expected_info_gain(belief: Belief, competency: str, strength: float | None = None) -> tuple[float, dict[str, float]]:
    s = config.update_setting("predicted_probe_strength") if strength is None else strength
    row = belief.probs[competency]
    h_before = _entropy(row)
    predicted = predict_polarity(belief, competency)
    expected_after = 0.0
    for polarity, p_o in predicted.items():
        if p_o <= 0:
            continue
        lik = config.likelihood_row(competency, polarity)
        post = [p * (l ** s) for p, l in zip(row, lik)]
        total = sum(post)
        post = [p / total for p in post]
        expected_after += p_o * _entropy(post)
    return max(0.0, h_before - expected_after), predicted


def choose(
    belief: Belief,
    *,
    after_turn_index: int,
    recent_choices: list[str],
    time_remaining_sec: int,
    mode: str,
) -> Decision:
    options: list[FollowUpOption] = []
    streak_comp = None
    if len(recent_choices) >= MAX_CONSECUTIVE_PROBES and len(set(recent_choices[-MAX_CONSECUTIVE_PROBES:])) == 1:
        streak_comp = recent_choices[-1]

    for comp in belief.probs:
        eig, predicted = expected_info_gain(belief, comp)
        meta = config.competency(comp)
        blocked = None
        if comp == streak_comp:
            blocked = f"probed {MAX_CONSECUTIVE_PROBES} times in a row"
        options.append(
            FollowUpOption(
                competency=comp,
                label=meta["label"],
                intent=meta["probe_intent"],
                eig=round(eig, 4),
                predicted={k: round(v, 4) for k, v in predicted.items()},
                blocked_reason=blocked,
            )
        )
    options.sort(key=lambda o: o.eig, reverse=True)

    if time_remaining_sec <= NO_STEER_LAST_SEC:
        return Decision(after_turn_index=after_turn_index, mode=mode, options=options, chosen=None,
                        reason="Under 2 minutes left - no steering while wrapping up.")
    eligible = [o for o in options if o.blocked_reason is None]
    if not eligible:
        return Decision(after_turn_index=after_turn_index, mode=mode, options=options, chosen=None,
                        reason="No eligible competency after constraints.")
    chosen = eligible[0]
    return Decision(
        after_turn_index=after_turn_index,
        mode=mode,
        options=options,
        chosen=chosen,
        reason=f"Highest expected information gain ({chosen.eig:.2f} bits) on {chosen.label}.",
    )
