"""
Real Interview Experience + Outcome Capture - specs/002-full-loop-platform
P0.11/P0.12. orchestrator.create_real_interview_experience/list_.../
get_owned_.../update_.../delete_.../upsert_real_interview_outcome/
real_interview_prediction.

Same isolated-private-engine pattern as test_loop_delete.py/test_loop_
committee.py - this file's rows never touch any other test file's data no
matter collection order.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api import orchestrator
from apps.api.db import Base
from apps.api.models import EvaluationRecord, LoopAttempt, PlannedRound, RoundAttempt
from apps.api.schemas import RealInterviewExperienceIn, RealInterviewOutcomeIn, RealInterviewRoundIn

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)


def _experience_req(**overrides) -> RealInterviewExperienceIn:
    defaults = dict(
        company="Anthropic",
        role_family="ml_engineer",
        level="staff",
        domain="ml_infra",
        interview_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        linked_loop_attempt_id=None,
        rounds=[RealInterviewRoundIn(round_type_label="System Design", question_family="Rate limiter design")],
        notes="Went reasonably well.",
        self_assessment="Felt solid on design, less sure on the follow-ups.",
        visibility="private",
    )
    defaults.update(overrides)
    return RealInterviewExperienceIn(**defaults)


def _make_evaluated_round(db, loop_id: str, user_id: str, *, round_type: str, readiness_pct: int, sort_order: int) -> PlannedRound:
    round_ = RoundAttempt(
        loop_attempt_id=loop_id,
        user_id=user_id,
        round_type=round_type,
        role_family="ml_engineer",
        level="staff",
        domain="ml_infra",
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
            hire_signal="HIRE",
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
        level="staff",
        domain="ml_infra",
        duration_minutes=45,
        sort_order=sort_order,
        round_attempt_id=round_.id,
    )
    db.add(planned)
    db.commit()
    return planned


def test_create_list_get_round_trip():
    db = SessionLocal()
    try:
        experience = orchestrator.create_real_interview_experience(db, "u1", _experience_req())
        assert experience.company == "Anthropic"
        assert experience.rounds[0]["question_family"] == "Rate limiter design"

        listed = orchestrator.list_real_interview_experiences(db, "u1")
        assert [e.id for e in listed] == [experience.id]

        fetched = orchestrator.get_owned_real_interview_experience(db, "u1", experience.id)
        assert fetched is not None
        assert fetched.id == experience.id
    finally:
        db.close()


def test_ownership_check_blocks_a_different_user():
    db = SessionLocal()
    try:
        experience = orchestrator.create_real_interview_experience(db, "u2", _experience_req())
        assert orchestrator.get_owned_real_interview_experience(db, "someone-else", experience.id) is None
        assert orchestrator.get_owned_real_interview_experience(db, "u2", "not-a-real-id") is None
    finally:
        db.close()


def test_linking_to_a_loop_owned_by_someone_else_is_rejected():
    db = SessionLocal()
    try:
        other_loop = LoopAttempt(user_id="someone-else", name="Not yours")
        db.add(other_loop)
        db.commit()

        with pytest.raises(orchestrator.LinkedLoopNotFoundError):
            orchestrator.create_real_interview_experience(
                db, "u3", _experience_req(linked_loop_attempt_id=other_loop.id)
            )
    finally:
        db.close()


def test_update_changes_fields_and_delete_removes_experience_and_outcome():
    db = SessionLocal()
    try:
        experience = orchestrator.create_real_interview_experience(db, "u4", _experience_req())
        orchestrator.upsert_real_interview_outcome(
            db, experience, RealInterviewOutcomeIn(status="advanced", stage="onsite")
        )

        updated = orchestrator.update_real_interview_experience(
            db, experience, _experience_req(company="Ramp", notes="Updated notes")
        )
        assert updated.company == "Ramp"
        assert updated.notes == "Updated notes"

        orchestrator.delete_real_interview_experience(db, updated)
        assert orchestrator.get_owned_real_interview_experience(db, "u4", experience.id) is None
        from apps.api.models import RealInterviewOutcome

        assert db.get(RealInterviewOutcome, experience.id) is None
    finally:
        db.close()


def test_outcome_upsert_creates_then_updates_not_a_second_row():
    db = SessionLocal()
    try:
        experience = orchestrator.create_real_interview_experience(db, "u5", _experience_req())

        first = orchestrator.upsert_real_interview_outcome(
            db, experience, RealInterviewOutcomeIn(status="no_response")
        )
        assert first.status == "no_response"

        second = orchestrator.upsert_real_interview_outcome(
            db, experience, RealInterviewOutcomeIn(status="offer", offered_level="senior")
        )
        assert second.experience_id == first.experience_id
        assert second.status == "offer"
        assert second.offered_level == "senior"

        from apps.api.models import RealInterviewOutcome

        assert db.query(RealInterviewOutcome).filter(RealInterviewOutcome.experience_id == experience.id).count() == 1
    finally:
        db.close()


def test_prediction_is_none_with_no_link():
    db = SessionLocal()
    try:
        experience = orchestrator.create_real_interview_experience(db, "u6", _experience_req())
        assert orchestrator.real_interview_prediction(db, experience) is None
    finally:
        db.close()


def test_prediction_falls_back_to_best_round_when_loop_never_reached_committee():
    db = SessionLocal()
    try:
        loop = LoopAttempt(user_id="u7", name="Single round loop")
        db.add(loop)
        db.flush()
        _make_evaluated_round(db, loop.id, "u7", round_type="ml_system_design", readiness_pct=65, sort_order=0)
        db.commit()

        experience = orchestrator.create_real_interview_experience(
            db, "u7", _experience_req(linked_loop_attempt_id=loop.id)
        )
        prediction = orchestrator.real_interview_prediction(db, experience)
        assert prediction is not None
        assert prediction.source == "round"
        assert prediction.readiness_pct == 65
    finally:
        db.close()


def test_prediction_uses_committee_verdict_once_the_loop_is_committee_eligible(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = SessionLocal()
    try:
        loop = LoopAttempt(user_id="u8", name="Two round loop")
        db.add(loop)
        db.flush()
        _make_evaluated_round(db, loop.id, "u8", round_type="ml_system_design", readiness_pct=80, sort_order=0)
        _make_evaluated_round(db, loop.id, "u8", round_type="coding", readiness_pct=60, sort_order=1)
        db.commit()
        orchestrator.generate_committee_report(db, loop)

        experience = orchestrator.create_real_interview_experience(
            db, "u8", _experience_req(linked_loop_attempt_id=loop.id)
        )
        prediction = orchestrator.real_interview_prediction(db, experience)
        assert prediction is not None
        assert prediction.source == "committee"
        assert prediction.readiness_pct == 70
    finally:
        db.close()
