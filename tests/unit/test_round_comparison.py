"""
tasks.md P1 item 16 - Retry/comparison ("a lightweight version of Longitudinal
Progress... two-attempt comparison, not full trend tracking yet"). Covers
orchestrator.compare_rounds(): always orders older -> newer by created_at
regardless of argument order, computes readiness/dimension deltas as
newer-minus-older, and returns None (not a raw KeyError/crash) when either
round hasn't been evaluated yet. Pure arithmetic over persisted
EvaluationRecord rows - no LLM call, no network, same isolated-temp-sqlite
pattern as test_orchestrator_interviewer_unavailable.py.
"""
from __future__ import annotations

import os
import tempfile

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from datetime import datetime, timezone  # noqa: E402

from apps.api import orchestrator  # noqa: E402
from apps.api.db import Base, SessionLocal, engine  # noqa: E402
from apps.api.models import RoundAttempt, TranscriptTurn  # noqa: E402
from apps.api.schemas import StartRoundRequest  # noqa: E402

Base.metadata.create_all(bind=engine)

_START_REQ = StartRoundRequest(
    role_family="ml_engineer",
    level="principal",
    domain="ml_infra",
    company_profile="generic",
    duration_minutes=45,
    mode="text",
)


def _new_evaluated_round(db, user_id: str) -> str:
    round_, _first_turn = orchestrator.create_round(db, user_id, _START_REQ)
    round_id = round_.id
    # RZ-02 (UI/UX review, 2026-09-29): submit_round now short-circuits a
    # round with no candidate turns at all to a "not assessed" result
    # (dimension_scores=[]), instead of scoring it like a real attempt - so
    # this fixture needs one real candidate turn to keep testing actual
    # dimension-score comparison, not the not-assessed path.
    db.add(
        TranscriptTurn(
            round_id=round_id,
            turn_index=1,
            speaker="candidate",
            text="I'd start by clarifying the latency and throughput requirements.",
            phase="ACTIVE",
        )
    )
    db.commit()
    round_ = db.get(RoundAttempt, round_id)
    orchestrator.submit_round(db, round_)
    return round_id


def test_compare_rounds_orders_older_to_newer_regardless_of_argument_order():
    db = SessionLocal()
    try:
        id_first = _new_evaluated_round(db, "cmp-user-1")
        id_second = _new_evaluated_round(db, "cmp-user-1")

        # Force unambiguous, deterministic timestamps - two create_round() calls
        # in the same test can land within the same microsecond, which would
        # make the "argument order doesn't matter" assertion below flaky.
        first = db.get(RoundAttempt, id_first)
        second = db.get(RoundAttempt, id_second)
        first.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        second.created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
        db.commit()
        db.refresh(first)
        db.refresh(second)
        assert first.created_at < second.created_at

        forward = orchestrator.compare_rounds(db, first, second)
        backward = orchestrator.compare_rounds(db, second, first)

        assert forward is not None and backward is not None
        assert forward.round_older.id == id_first
        assert forward.round_newer.id == id_second
        # Argument order must not change the result.
        assert backward.round_older.id == forward.round_older.id
        assert backward.round_newer.id == forward.round_newer.id
        assert backward.readiness_delta == forward.readiness_delta
    finally:
        db.close()


def test_compare_rounds_dimension_deltas_are_newer_minus_older():
    db = SessionLocal()
    try:
        id_a = _new_evaluated_round(db, "cmp-user-2")
        id_b = _new_evaluated_round(db, "cmp-user-2")
        round_a = db.get(RoundAttempt, id_a)
        round_b = db.get(RoundAttempt, id_b)

        comparison = orchestrator.compare_rounds(db, round_a, round_b)
        assert comparison is not None
        assert comparison.readiness_delta == (
            comparison.evaluation_newer.readiness_pct - comparison.evaluation_older.readiness_pct
        )
        assert len(comparison.dimension_deltas) > 0
        for d in comparison.dimension_deltas:
            assert d.delta == d.score_newer - d.score_older
    finally:
        db.close()


def test_compare_rounds_returns_none_when_a_round_is_not_yet_evaluated():
    db = SessionLocal()
    try:
        evaluated_id = _new_evaluated_round(db, "cmp-user-3")
        not_evaluated, _first_turn = orchestrator.create_round(db, "cmp-user-3", _START_REQ)

        evaluated = db.get(RoundAttempt, evaluated_id)
        result = orchestrator.compare_rounds(db, evaluated, not_evaluated)
        assert result is None
    finally:
        db.close()
