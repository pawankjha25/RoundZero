"""
DELETE /v1/loops/{loop_id} (apps/api/routes/loops.py) / orchestrator.delete_loop:
deleting a loop must remove it and every planned round in it, and for any
planned round that was actually started, that round's full history too
(transcript, workspace state/events, evaluation) - not leave orphaned rows
behind. Added alongside the delete-loop feature itself (no delete-loop
capability existed before this).

Same isolated-private-engine pattern as test_coding_round_e2e.py - this
file's rows never touch any other test file's data no matter collection
order, and nothing here needs a real LLM call so there's no network
dependency either.
"""
from __future__ import annotations

import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api import orchestrator
from apps.api.db import Base
from apps.api.models import (
    EvaluationRecord,
    LoopAttempt,
    LoopCommitteeRecord,
    PlannedRound,
    RoundAttempt,
    RoundWorkspaceState,
    TranscriptTurn,
    WorkspaceEvent,
)

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)


def _make_started_round(db, loop_id: str, user_id: str) -> str:
    round_ = RoundAttempt(
        loop_attempt_id=loop_id,
        user_id=user_id,
        round_type="coding",
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

    db.add(TranscriptTurn(round_id=round_.id, turn_index=0, speaker="interviewer", text="hi", phase="INTRO"))
    db.add(TranscriptTurn(round_id=round_.id, turn_index=1, speaker="candidate", text="hello", phase="INTRO"))
    db.add(RoundWorkspaceState(round_id=round_.id, code_language="python", code_text="print(1)"))
    db.add(WorkspaceEvent(round_id=round_.id, kind="code_change", payload={"n": 1}))
    db.add(
        EvaluationRecord(
            round_id=round_.id,
            dimension_scores=[],
            readiness_pct=50,
            hire_signal="LEAN HIRE",
            primary_concern="fixture",
            strengths=[],
            weaknesses=[],
            improvement_plan=[],
        )
    )
    db.commit()
    return round_.id


def test_delete_loop_removes_the_loop_and_every_planned_round():
    db = SessionLocal()
    try:
        loop = LoopAttempt(user_id="u1", name="Loop to delete")
        db.add(loop)
        db.flush()

        started_round_id = _make_started_round(db, loop.id, "u1")
        started_planned = PlannedRound(
            loop_attempt_id=loop.id,
            user_id="u1",
            round_type="coding",
            role_family="ml_engineer",
            level="senior",
            domain="general_ml",
            company_profile="generic",
            duration_minutes=45,
            modality="text",
            sort_order=0,
            round_attempt_id=started_round_id,
        )
        unstarted_planned = PlannedRound(
            loop_attempt_id=loop.id,
            user_id="u1",
            round_type="ml_system_design",
            role_family="ml_engineer",
            level="senior",
            domain="general_ml",
            company_profile="generic",
            duration_minutes=45,
            modality="text",
            sort_order=1,
        )
        db.add_all([started_planned, unstarted_planned])
        db.commit()
        loop_id = loop.id

        orchestrator.delete_loop(db, loop)

        assert db.get(LoopAttempt, loop_id) is None
        assert db.query(PlannedRound).filter(PlannedRound.loop_attempt_id == loop_id).count() == 0
        assert db.get(RoundAttempt, started_round_id) is None
        assert db.query(TranscriptTurn).filter(TranscriptTurn.round_id == started_round_id).count() == 0
        assert db.get(RoundWorkspaceState, started_round_id) is None
        assert db.query(WorkspaceEvent).filter(WorkspaceEvent.round_id == started_round_id).count() == 0
        assert db.get(EvaluationRecord, started_round_id) is None
    finally:
        db.close()


def test_delete_loop_does_not_touch_a_different_loop():
    db = SessionLocal()
    try:
        kept_loop = LoopAttempt(user_id="u2", name="Loop to keep")
        doomed_loop = LoopAttempt(user_id="u2", name="Loop to delete")
        db.add_all([kept_loop, doomed_loop])
        db.flush()

        kept_round_id = _make_started_round(db, kept_loop.id, "u2")
        db.add(
            PlannedRound(
                loop_attempt_id=kept_loop.id,
                user_id="u2",
                round_type="coding",
                role_family="ml_engineer",
                level="senior",
                domain="general_ml",
                company_profile="generic",
                duration_minutes=45,
                modality="text",
                sort_order=0,
                round_attempt_id=kept_round_id,
            )
        )
        db.add(
            PlannedRound(
                loop_attempt_id=doomed_loop.id,
                user_id="u2",
                round_type="ml_system_design",
                role_family="ml_engineer",
                level="senior",
                domain="general_ml",
                company_profile="generic",
                duration_minutes=45,
                modality="text",
                sort_order=0,
            )
        )
        db.commit()
        kept_loop_id = kept_loop.id

        orchestrator.delete_loop(db, doomed_loop)

        assert db.get(LoopAttempt, kept_loop_id) is not None
        assert db.query(PlannedRound).filter(PlannedRound.loop_attempt_id == kept_loop_id).count() == 1
        assert db.get(RoundAttempt, kept_round_id) is not None
        assert db.get(EvaluationRecord, kept_round_id) is not None
    finally:
        db.close()


def test_delete_loop_also_removes_its_cached_committee_record():
    """Added alongside specs/002 P0.6's Virtual Hiring Committee - a loop's
    LoopCommitteeRecord (apps/api/models.py) is a child row exactly like
    everything else this file already covers, and deleting the loop must not
    leave it orphaned behind."""
    db = SessionLocal()
    try:
        loop = LoopAttempt(user_id="u4", name="Loop with a committee record")
        db.add(loop)
        db.flush()
        db.add(
            LoopCommitteeRecord(
                loop_attempt_id=loop.id,
                rounds_included=["r1", "r2"],
                overall_readiness_pct=70,
                overall_hire_signal="HIRE",
                confidence="medium",
                headline="fixture headline",
                strengths=[],
                concerns=[],
                level_signal="fixture level signal",
                key_evidence=[],
            )
        )
        db.commit()
        loop_id = loop.id

        orchestrator.delete_loop(db, loop)

        assert db.get(LoopAttempt, loop_id) is None
        assert db.get(LoopCommitteeRecord, loop_id) is None
    finally:
        db.close()
