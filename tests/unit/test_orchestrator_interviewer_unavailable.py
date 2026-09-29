"""
Regression test for the 2026-09-01 "Failed to fetch on Voice" investigation:
a real cause was Gemini's free-tier daily quota (429 RESOURCE_EXHAUSTED, 20
requests/day) being exhausted, but the actual *bug* was that create_round()/
post_message() had nothing catching a provider failure around
interviewer.next_turn() - the raw exception escaped unhandled all the way to
the ASGI server. That's a bad candidate-facing experience on its own (an
opaque 500), and worse: because it bypasses FastAPI's normal exception
handling, Starlette's CORSMiddleware never gets to attach CORS headers to the
error response, so the browser's fetch() rejects with a bare "Failed to
fetch" instead of surfacing any real status or detail at all.

This test proves the fix: any interviewer.next_turn() failure - regardless of
which provider or exception type caused it - surfaces as orchestrator's own
InterviewerUnavailableError, which apps/api/routes/rounds.py turns into a
normal, CORS-safe HTTPException(503, ...). It also proves the failed
create_round() call leaves no orphan RoundAttempt/LoopAttempt rows behind (the
session is closed - never committed - on the way out, same as
apps/api/db.py::get_db()'s finally: db.close(), which SQLAlchemy documents as
implicitly rolling back any pending transaction).

Uses a throwaway, isolated SQLite file (never the real apps/api/roundzero.db)
so this can run in the same "no network, no shared state" spirit as every
other test in this suite - DATABASE_URL must be set before apps.api.db is
first imported anywhere in the test process, so that happens at module import
time, before any apps.api.* import below.
"""
from __future__ import annotations

import os
import tempfile

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

import pytest  # noqa: E402

from apps.api import orchestrator  # noqa: E402
from apps.api.db import Base, SessionLocal, engine  # noqa: E402
from apps.api.models import LoopAttempt, RoundAttempt, TranscriptTurn  # noqa: E402
from apps.api.schemas import StartRoundRequest  # noqa: E402
from roundzero.llm.gateway import LLMGateway  # noqa: E402

Base.metadata.create_all(bind=engine)


class FailingGateway(LLMGateway):
    """Simulates any provider outage/quota exhaustion - the exact exception
    type doesn't matter, since the fix wraps interviewer.next_turn() with a
    bare `except Exception`, not a provider-specific one."""

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        raise RuntimeError("429 RESOURCE_EXHAUSTED (simulated)")


_START_REQ = StartRoundRequest(
    role_family="ml_engineer",
    level="principal",
    domain="ml_infra",
    company_profile="generic",
    duration_minutes=45,
    mode="text",
)


def test_create_round_raises_interviewer_unavailable_not_a_raw_provider_error(monkeypatch):
    monkeypatch.setattr(orchestrator, "get_gateway", lambda **kwargs: FailingGateway())

    db = SessionLocal()
    try:
        with pytest.raises(orchestrator.InterviewerUnavailableError):
            orchestrator.create_round(db, "test-user", _START_REQ)
    finally:
        db.close()

    # No orphan rows left behind by the failed attempt.
    verify_db = SessionLocal()
    try:
        assert verify_db.query(RoundAttempt).count() == 0
        assert verify_db.query(LoopAttempt).count() == 0
    finally:
        verify_db.close()


def test_post_message_raises_interviewer_unavailable_not_a_raw_provider_error(monkeypatch):
    # First, create a real round with a working gateway so there's something
    # to post a message to.
    db = SessionLocal()
    try:
        round_, _first_turn = orchestrator.create_round(db, "test-user-2", _START_REQ)
        round_id = round_.id
    finally:
        db.close()

    monkeypatch.setattr(orchestrator, "get_gateway", lambda **kwargs: FailingGateway())

    db = SessionLocal()
    try:
        round_ = db.get(RoundAttempt, round_id)
        with pytest.raises(orchestrator.InterviewerUnavailableError):
            orchestrator.post_message(db, round_, "Here's my design.")
    finally:
        db.close()


# --- submit_round() / evaluation path -----------------------------------
#
# Same shape of bug as create_round()/post_message() above, but on the
# scoring path: get_evaluator() (LLMEvaluator/GPT-5 mini when
# OPENAI_API_KEY is set) and llm_report_synthesis() (a second, separate
# OpenAI call) can fail the same way Gemini did. Worse here: round_.status
# was already committed as "EVALUATING" *before* either call runs, so an
# unhandled failure left the round permanently wedged - not just an opaque
# error, a round that could never be scored again. submit_round() now
# resets status back to "SUBMITTED" before raising, so a retried Submit
# re-enters cleanly.

from roundzero.evaluation.evaluator import Evaluator  # noqa: E402
from roundzero.evaluation.models import ScoredRound  # noqa: E402


class FailingEvaluator(Evaluator):
    def evaluate(self, *, round_id, round_type, transcript, final_coverage):
        raise RuntimeError("429 RESOURCE_EXHAUSTED (simulated)")


def _create_completed_round(db, user_id: str) -> str:
    round_, _first_turn = orchestrator.create_round(db, user_id, _START_REQ)
    # RZ-02 (UI/UX review, 2026-09-29): submit_round now short-circuits a
    # round with no candidate turns at all straight to a "not assessed"
    # result, without ever calling get_evaluator() - so this fixture needs
    # one real candidate turn to keep exercising what this file actually
    # tests (evaluator/provider failure and retry), not the not-assessed
    # path.
    db.add(
        TranscriptTurn(
            round_id=round_.id,
            turn_index=1,
            speaker="candidate",
            text="I'd start by clarifying the latency and throughput requirements.",
            phase="ACTIVE",
        )
    )
    db.commit()
    return round_.id


def test_submit_round_raises_evaluation_unavailable_not_a_raw_provider_error(monkeypatch):
    db = SessionLocal()
    try:
        round_id = _create_completed_round(db, "test-user-3")
    finally:
        db.close()

    monkeypatch.setattr(orchestrator, "get_evaluator", lambda: FailingEvaluator())

    db = SessionLocal()
    try:
        round_ = db.get(RoundAttempt, round_id)
        with pytest.raises(orchestrator.EvaluationUnavailableError):
            orchestrator.submit_round(db, round_)

        # Not wedged in EVALUATING - reset back to SUBMITTED so a retry works.
        db.refresh(round_)
        assert round_.status == "SUBMITTED"
    finally:
        db.close()


def test_submit_round_retry_after_failure_succeeds(monkeypatch):
    db = SessionLocal()
    try:
        round_id = _create_completed_round(db, "test-user-4")
    finally:
        db.close()

    monkeypatch.setattr(orchestrator, "get_evaluator", lambda: FailingEvaluator())
    db = SessionLocal()
    try:
        round_ = db.get(RoundAttempt, round_id)
        with pytest.raises(orchestrator.EvaluationUnavailableError):
            orchestrator.submit_round(db, round_)
    finally:
        db.close()

    # Provider "recovers": get_evaluator back to normal (RuleBasedEvaluator,
    # since no OPENAI_API_KEY is set in this test process).
    monkeypatch.undo()

    db = SessionLocal()
    try:
        round_ = db.get(RoundAttempt, round_id)
        evaluation = orchestrator.submit_round(db, round_)
        assert evaluation.readiness_pct is not None
        db.refresh(round_)
        assert round_.status == "EVALUATED"
    finally:
        db.close()
