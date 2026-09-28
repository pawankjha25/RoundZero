"""
Golden regression suite for the ml_system_design round's scoring - the
"golden/" piece of evals/README.md's layout, and item 5/7 of the Definition
of Done (.claude/skills/add-interview-round: "Golden evaluation cases exist" /
"Evaluator passes regression thresholds against the golden set"). Was two
README stubs and zero fixtures before this pass (see
evals/golden/ml_system_design/README.md's own "Not created yet" note).

Scope, deliberately: this suite targets RuleBasedEvaluator only, the
deterministic fallback that runs with no LLM key at all (see
apps/api/orchestrator.get_evaluator()). Because it's a pure function of
(transcript, final_coverage) - no model call, no randomness - "expected" here
is an exact match, not a score band: any change to the rubric weights,
CoverageStatus->score mapping, the 3-evidence "exceeds target" bump, or
compute_readiness()'s hire-signal thresholds should make one of these
fixtures fail, on purpose, so the change gets a conscious look before it
ships (CLAUDE.md decision 3: "Every prompt/model/rubric change is
regression-tested against golden interview transcripts before it ships").

LLMEvaluator (GPT-5 mini) is NOT covered here - it's non-deterministic and
needs a real OPENAI_API_KEY plus band-based (not exact) assertions, which is
a real follow-up but a different kind of test than this one. Flagging that
explicitly rather than silently pretending this suite covers both evaluators.

Fixtures live one-per-file under fixtures/*.json (see generate_fixtures.py in
this directory to see how they were built/regenerate them) - each is a
transcript + final_coverage the fixture's own "description" explains, plus
the exact expected dimension_scores/readiness_pct/hire_signal.

Run explicitly: `pytest evals/ -q` from the repo root (this venv also needs
DATABASE_URL set, same as tests/unit - see that suite's own note). Not bundled
into `pytest tests/unit -q`'s fast dev-loop run on purpose - evals/README.md
describes this as a separate, "before it ships" gate, not the per-change unit
suite.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from roundzero.evaluation.evaluator import RuleBasedEvaluator

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_PATHS = sorted(FIXTURES_DIR.glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.mark.parametrize("fixture_path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_golden_fixture_matches_rule_based_evaluator_exactly(fixture_path: Path):
    fixture = _load(fixture_path)
    evaluator = RuleBasedEvaluator()

    scored = evaluator.evaluate(
        round_id=f"golden-{fixture['id']}",
        round_type="ml_system_design",
        transcript=fixture["transcript"],
        final_coverage=fixture["final_coverage"],
    )

    expected = fixture["expected"]
    actual_scores = {d.dimension: d.score for d in scored.dimension_scores}

    assert actual_scores == expected["dimension_scores"], (
        f"{fixture['id']}: per-dimension scores drifted from the golden fixture.\n"
        f"description: {fixture['description']}"
    )
    assert scored.readiness_pct == expected["readiness_pct"], (
        f"{fixture['id']}: readiness_pct drifted ({scored.readiness_pct} != {expected['readiness_pct']}).\n"
        f"description: {fixture['description']}"
    )
    assert scored.hire_signal == expected["hire_signal"], (
        f"{fixture['id']}: hire_signal drifted ({scored.hire_signal!r} != {expected['hire_signal']!r}).\n"
        f"description: {fixture['description']}"
    )


def test_at_least_ten_golden_fixtures_exist():
    # Definition of Done (.claude/skills/add-interview-round): "Golden
    # evaluation cases exist" - mirrors the 10-scenario bar tasks.md item 4
    # set for interview scenarios themselves.
    assert len(FIXTURE_PATHS) >= 10


def test_golden_fixtures_span_every_hire_signal_band():
    # A golden set that only ever exercised "great" or "terrible" transcripts
    # wouldn't actually protect the interesting boundaries - this is the
    # concrete assertion that all five hire-signal bands are represented.
    signals = {_load(p)["expected"]["hire_signal"] for p in FIXTURE_PATHS}
    expected_bands = {"STRONG HIRE", "HIRE", "LEAN HIRE", "LEAN NO HIRE", "NO HIRE"}
    missing = expected_bands - signals
    assert not missing, f"no golden fixture lands in: {missing}"
