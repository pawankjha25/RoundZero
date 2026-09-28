"""
Virtual Hiring Committee eligibility/caching - specs/002-full-loop-platform P0.6.
orchestrator.loop_committee_eligible/get_committee_report/generate_committee_report.

Same isolated-private-engine pattern as test_loop_delete.py - this file's rows
never touch any other test file's data no matter collection order. The
OPENAI_API_KEY env var is explicitly cleared so generate_committee_report always
takes the rule-based path here (deterministic, no network) regardless of what's
in the real environment/.env - the LLM call path itself is covered separately
in test_committee_synthesis.py with a FakeGateway.
"""
from __future__ import annotations

import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api import orchestrator
from apps.api.db import Base
from apps.api.models import EvaluationRecord, LoopAttempt, PlannedRound, RoundAttempt

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)


@pytest.fixture(autouse=True)
def _no_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _make_evaluated_round(db, loop_id: str, user_id: str, *, round_type: str, readiness_pct: int, sort_order: int) -> PlannedRound:
    round_ = RoundAttempt(
        loop_attempt_id=loop_id,
        user_id=user_id,
        round_type=round_type,
        role_family="ml_engineer",
        level="senior",
        domain="general_ml",
        scenario_id="fixture_scenario",
        scenario_prompt="fixture prompt",
        duration_minutes=45,
        status="EVALUATED",
        phase="WRAP_UP",
        coverage={},
    )
    db.add(round_)
    db.flush()
    db.add(
        EvaluationRecord(
            round_id=round_.id,
            dimension_scores=[],
            readiness_pct=readiness_pct,
            hire_signal="HIRE",  # not asserted on directly - only readiness_pct/confidence are
            primary_concern="fixture concern",
            strengths=[],
            weaknesses=[],
            improvement_plan=[],
        )
    )
    planned = PlannedRound(
        loop_attempt_id=loop_id,
        user_id=user_id,
        round_type=round_type,
        role_family="ml_engineer",
        level="senior",
        domain="general_ml",
        duration_minutes=45,
        sort_order=sort_order,
        round_attempt_id=round_.id,
    )
    db.add(planned)
    db.commit()
    return planned


def test_loop_with_only_one_evaluated_real_round_is_not_eligible():
    db = SessionLocal()
    try:
        loop = LoopAttempt(user_id="u1", name="One round loop")
        db.add(loop)
        db.flush()
        _make_evaluated_round(db, loop.id, "u1", round_type="ml_system_design", readiness_pct=70, sort_order=0)

        assert orchestrator.loop_committee_eligible(db, loop) == []
        assert orchestrator.get_committee_report(db, loop) is None
        with pytest.raises(orchestrator.CommitteeNotReadyError):
            orchestrator.generate_committee_report(db, loop)
    finally:
        db.close()


def test_loop_with_two_evaluated_real_rounds_generates_deterministic_aggregate():
    db = SessionLocal()
    try:
        loop = LoopAttempt(user_id="u2", name="Two round loop")
        db.add(loop)
        db.flush()
        _make_evaluated_round(db, loop.id, "u2", round_type="ml_system_design", readiness_pct=80, sort_order=0)
        _make_evaluated_round(db, loop.id, "u2", round_type="coding", readiness_pct=60, sort_order=1)

        report, rounds_included, _ = orchestrator.generate_committee_report(db, loop)
        assert report.overall_readiness_pct == 70
        assert report.confidence == "medium"
        assert len(rounds_included) == 2

        cached = orchestrator.get_committee_report(db, loop)
        assert cached is not None
        assert cached[0].overall_readiness_pct == 70
    finally:
        db.close()


def test_repeated_generate_with_no_new_rounds_does_not_recompute(monkeypatch):
    calls = {"n": 0}
    real_rule_based = orchestrator.rule_based_committee_synthesis

    def counting_rule_based(rounds, target_level):
        calls["n"] += 1
        return real_rule_based(rounds, target_level)

    monkeypatch.setattr(orchestrator, "rule_based_committee_synthesis", counting_rule_based)

    db = SessionLocal()
    try:
        loop = LoopAttempt(user_id="u3", name="Cache test loop")
        db.add(loop)
        db.flush()
        _make_evaluated_round(db, loop.id, "u3", round_type="ml_system_design", readiness_pct=80, sort_order=0)
        _make_evaluated_round(db, loop.id, "u3", round_type="coding", readiness_pct=60, sort_order=1)

        orchestrator.generate_committee_report(db, loop)
        orchestrator.generate_committee_report(db, loop)
        assert calls["n"] == 1  # second call served the cached, still-fresh record

        # Adding a 3rd evaluated round makes the cached record stale.
        _make_evaluated_round(db, loop.id, "u3", round_type="ml_depth", readiness_pct=90, sort_order=2)
        assert orchestrator.get_committee_report(db, loop) is None  # stale, not yet regenerated

        report, rounds_included, _ = orchestrator.generate_committee_report(db, loop)
        assert calls["n"] == 2
        assert len(rounds_included) == 3
        assert report.confidence == "high"
    finally:
        db.close()
