"""
Level Calibration (specs/002 P0.4, first honest version) - user-requested,
from the "keep going for next 5 features" build sprint. Deliberately does NOT
invent new per-level rubric thresholds (the fabricated-precision trap the
Virtual Hiring Committee's own docstring already declined) - instead maps the
EXISTING, already-real readiness_pct/hire_signal scale (every evaluator
prompt is explicitly written at one fixed "Staff/Principal-level" bar,
confirmed by grep showing evaluator.py never receives a level at all) onto
the app's 3-level ladder, using the ALREADY-ESTABLISHED HIRE_SIGNAL_THRESHOLDS
cut points (80/65/50) - no new invented numbers.

Covers every band boundary and the "where confidence permits" floor (nothing
claimed below LEAN HIRE).
"""
from __future__ import annotations

from roundzero.leveling.calibration import calibrate_level


def test_strong_hire_clears_principal_and_offers_no_higher_stretch():
    result = calibrate_level(85, "STRONG HIRE")
    assert result.competitive_target == "principal"
    assert result.safe_target == "staff"
    assert result.stretch_target is None
    assert "85%" in result.narrative
    assert "STRONG HIRE" in result.narrative


def test_hire_band_offers_a_stretch_toward_principal():
    result = calibrate_level(70, "HIRE")
    assert result.competitive_target == "staff"
    assert result.safe_target == "senior"
    assert result.stretch_target == "principal"


def test_lean_hire_band_has_no_stretch():
    result = calibrate_level(55, "LEAN HIRE")
    assert result.competitive_target == "staff"
    assert result.safe_target == "senior"
    assert result.stretch_target is None


def test_below_lean_hire_claims_nothing():
    for pct, signal in [(49, "LEAN NO HIRE"), (20, "NO HIRE"), (0, "NO HIRE")]:
        result = calibrate_level(pct, signal)
        assert result.competitive_target is None
        assert result.safe_target is None
        assert result.stretch_target is None
        assert str(pct) + "%" in result.narrative


def test_band_boundaries_match_existing_hire_signal_thresholds_exactly():
    # 80/65/50 are HIRE_SIGNAL_THRESHOLDS' own cut points
    # (roundzero.evaluation.evaluator) - this locks calibrate_level to those,
    # not a second, independently-drifting set of numbers.
    assert calibrate_level(80, "STRONG HIRE").competitive_target == "principal"
    assert calibrate_level(79, "HIRE").competitive_target == "staff"
    assert calibrate_level(65, "HIRE").competitive_target == "staff"
    assert calibrate_level(64, "LEAN HIRE").competitive_target == "staff"
    assert calibrate_level(50, "LEAN HIRE").competitive_target == "staff"
    assert calibrate_level(49, "LEAN NO HIRE").competitive_target is None


def test_narrative_discloses_the_fixed_bar_the_round_was_scored_against():
    result = calibrate_level(70, "HIRE")
    assert "Staff/Principal" in result.narrative
