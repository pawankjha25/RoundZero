"""
Level Calibration - specs/002 P0.4 ("Evaluate against the target level AND
adjacent levels... Report Safe Target / Competitive Target / Stretch Target
where confidence permits... Base calibration on explicit level-expectation
definitions, not free-form LLM opinion.").

This is deliberately NOT what P0.6's Virtual Hiring Committee explicitly
declined to build: a fabricated level range invented from nothing (see that
feature's own docstring in apps/api/orchestrator.py, and P0.13's warning
against "unsupported statistical confidence"). Round Zero does not maintain
separate rubric anchors per level today, so there is no real per-level
assessment to report a range from - inventing thresholds against the raw
readiness_pct would be exactly that fabricated precision.

What DOES already exist, and is real, documented, and level-independent: every
evaluator prompt (prompts/evaluators/*/v1.md) opens with "You are an
independent evaluator for a Staff/Principal-level [round type] interview" -
verbatim, for every round, regardless of which level the candidate picked at
Setup (apps/api/orchestrator.py's evaluator call never passes level at all).
readiness_pct and hire_signal are already a deterministic score against that
one fixed, documented bar. Calibrate_level's job is narrow: map THAT existing,
real scale onto the app's own 3-level ladder (senior/staff/principal, apps/api/
seed.py's _LEVELS) using the ALREADY-ESTABLISHED HIRE_SIGNAL_THRESHOLDS cut
points (roundzero.evaluation.evaluator) - not new invented numbers - and say so
plainly in the narrative, rather than implying a level-specific assessment
that never happened.

Conservative by design: below LEAN HIRE (readiness_pct < 50) nothing is
claimed at all (all three targets None) - "where confidence permits" from the
backlog item is honored by staying silent rather than guessing downward from a
test the candidate didn't clear. `stretch_target` is offered only in the HIRE
band (65-79), the one place a "not yet confirmed, but showing real signal"
claim is genuinely defensible; STRONG HIRE (80+) already means the round's
own top bar (Principal, since the ladder stops there) so there is nothing
higher to stretch toward.
"""
from __future__ import annotations

from pydantic import BaseModel

# Matches apps/api/seed.py's _LEVELS order exactly (low -> high). If a 4th
# level is ever added there, this needs a matching, deliberate update to the
# bands in calibrate_level below - never auto-derived, since the bands are
# hand-picked against the evaluator's one fixed Staff/Principal-caliber bar,
# not against N evenly-spaced levels.
LEVELS = ["senior", "staff", "principal"]

_LABELS = {"senior": "Senior", "staff": "Staff", "principal": "Principal"}


class LevelCalibration(BaseModel):
    safe_target: str | None = None
    competitive_target: str | None = None
    stretch_target: str | None = None
    narrative: str


def _label(level: str | None) -> str | None:
    return _LABELS.get(level) if level else None


def calibrate_level(readiness_pct: int, hire_signal: str) -> LevelCalibration:
    """Pure function of the round's own already-computed readiness_pct/
    hire_signal - no new evaluation, no LLM call, nothing stored redundantly
    (called fresh wherever a RoundEvaluation is composed, same "live-computed"
    discipline as orchestrator.real_interview_prediction)."""
    if readiness_pct >= 80:  # STRONG HIRE
        safe, competitive, stretch = "staff", "principal", None
    elif readiness_pct >= 65:  # HIRE
        safe, competitive, stretch = "senior", "staff", "principal"
    elif readiness_pct >= 50:  # LEAN HIRE
        safe, competitive, stretch = "senior", "staff", None
    else:  # LEAN NO HIRE or NO HIRE
        safe, competitive, stretch = None, None, None

    bar_note = (
        "This round is evaluated against Staff/Principal-level expectations "
        "(every interviewer and evaluator for this round type is, regardless of "
        "the level you selected at setup)."
    )
    if competitive is None:
        narrative = (
            f"{bar_note} At {readiness_pct}% readiness ({hire_signal}), this round doesn't "
            "clear that bar confidently enough to call a target level yet - closing the gaps "
            "below is the fastest path there."
        )
    else:
        pieces = [f"{bar_note} At {readiness_pct}% readiness ({hire_signal}), this performance "
                  f"clears the {_label(competitive)} bar."]
        if safe:
            pieces.append(f"{_label(safe)} is a safe target given the margin.")
        if stretch:
            pieces.append(
                f"{_label(stretch)} is a stretch worth reaching for - not yet confirmed at that "
                "bar, but showing real signal."
            )
        narrative = " ".join(pieces)

    return LevelCalibration(
        safe_target=safe,
        competitive_target=competitive,
        stretch_target=stretch,
        narrative=narrative,
    )
