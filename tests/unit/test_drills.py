"""
Drills - "Practice this weakness" (user-requested, from the "keep going for
next 5 features" build sprint). Closes the Assess -> Diagnose -> Practice ->
Reassess loop specs/002 P0.10 describes but never built: build_improvement_
plan (src/roundzero/improvement/plan.py) already runs at submit time and its
output sits unused in EvaluationRecord.improvement_plan - this is the first
thing that lets a candidate act on one of those items.

Covers orchestrator.start_drill_round: happy path (focus_hint built from the
matching improvement_plan item, target profile copied from the source round,
a real bank scenario picked - not a fabricated one, PlannedRound invariant
upheld), and both DrillSourceNotFoundError cases (source round never
evaluated; requested priority not present in that round's plan).

Same isolated-private-engine pattern as test_prep_plans.py/test_real_
interviews.py - this file's rows never touch any other test file's data no
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

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)


def _evaluated_round(db, user_id: str, *, round_type: str = "ml_system_design", improvement_plan=None) -> RoundAttempt:
    loop = LoopAttempt(user_id=user_id)
    db.add(loop)
    db.flush()
    round_ = RoundAttempt(
        loop_attempt_id=loop.id,
        user_id=user_id,
        round_type=round_type,
        role_family="ml_engineer",
        level="senior",
        domain="ml_infra",
        company_profile="startup",
        duration_minutes=45,
        modality="text",
        scenario_id="s1",
        scenario_prompt="p",
        status="EVALUATED",
        phase="WRAP_UP",
        coverage={},
        started_at=datetime.now(timezone.utc),
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(round_)
    db.flush()
    if improvement_plan is not None:
        db.add(
            EvaluationRecord(
                round_id=round_.id,
                dimension_scores=[],
                readiness_pct=45,
                hire_signal="LEAN NO HIRE",
                primary_concern="x",
                strengths=[],
                weaknesses=[],
                improvement_plan=improvement_plan,
            )
        )
    db.commit()
    db.refresh(round_)
    return round_


_PLAN = [
    {
        "dimension": "failure_modes",
        "priority": 1,
        "recommendation": "Practice going deeper on failure-mode tradeoffs without being prompted.",
        "based_on": "Never raised a single failure scenario unprompted.",
    },
    {
        "dimension": "communication",
        "priority": 2,
        "recommendation": "Keep sharpening communication - solid, but push toward more sophisticated framing.",
        "based_on": "Clear but surface-level explanations.",
    },
]


def test_start_drill_round_builds_focus_hint_and_copies_target_profile():
    db = SessionLocal()
    try:
        source = _evaluated_round(db, "u1", improvement_plan=_PLAN)

        drill_round, first_turn = orchestrator.start_drill_round(db, "u1", source, priority=1)

        assert drill_round.id != source.id
        assert drill_round.drill_focus_hint == (
            "failure_modes: Practice going deeper on failure-mode tradeoffs without being prompted."
        )
        # Same target profile as the source round - picking a drill is one click,
        # never a re-ask of role/level/domain/company/duration/modality.
        assert drill_round.round_type == source.round_type
        assert drill_round.role_family == source.role_family
        assert drill_round.level == source.level
        assert drill_round.domain == source.domain
        assert drill_round.company_profile == source.company_profile
        assert drill_round.duration_minutes == source.duration_minutes
        assert drill_round.modality == source.modality
        # A real scenario was picked (pick_scenario), not a fabricated one -
        # same "never hand-author a scenario dict" discipline
        # start_round_from_plan_question established for Coding.
        assert drill_round.scenario_id
        assert drill_round.scenario_prompt
        assert first_turn.speaker == "interviewer"

        # "every RoundAttempt has exactly one PlannedRound" invariant.
        planned = db.query(PlannedRound).filter(PlannedRound.round_attempt_id == drill_round.id).one_or_none()
        assert planned is not None
        assert planned.round_type == source.round_type
    finally:
        db.close()


def test_start_drill_round_second_priority_picks_the_matching_item():
    db = SessionLocal()
    try:
        source = _evaluated_round(db, "u2", improvement_plan=_PLAN)
        drill_round, _ = orchestrator.start_drill_round(db, "u2", source, priority=2)
        assert drill_round.drill_focus_hint.startswith("communication:")
    finally:
        db.close()


def test_start_drill_round_raises_when_source_round_never_evaluated():
    db = SessionLocal()
    try:
        source = _evaluated_round(db, "u3", improvement_plan=None)
        with pytest.raises(orchestrator.DrillSourceNotFoundError):
            orchestrator.start_drill_round(db, "u3", source, priority=1)
    finally:
        db.close()


def test_start_drill_round_raises_when_priority_not_in_plan():
    db = SessionLocal()
    try:
        source = _evaluated_round(db, "u4", improvement_plan=_PLAN)
        with pytest.raises(orchestrator.DrillSourceNotFoundError):
            orchestrator.start_drill_round(db, "u4", source, priority=99)
    finally:
        db.close()


def test_start_drill_round_works_for_coding_round_type_without_fabricating_a_scenario():
    # Coding's structured fields (title/entry_point/starter_code/test_cases)
    # only exist on real bank scenarios - proves the drill path reuses
    # pick_scenario() for Coding too rather than building a bare
    # {"id": ..., "prompt": ...} dict that would leave the workspace broken
    # (no starter code, no runnable tests).
    db = SessionLocal()
    try:
        source = _evaluated_round(db, "u5", round_type="coding", improvement_plan=_PLAN)
        drill_round, _ = orchestrator.start_drill_round(db, "u5", source, priority=1)
        assert drill_round.round_type == "coding"
        assert drill_round.scenario_meta.get("entry_point")
    finally:
        db.close()
