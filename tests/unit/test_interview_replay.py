"""
Interview Replay (user-requested, from the "keep going for next 5 features"
build sprint) - backlog P0.9's "OK to start with transcript + code/canvas
timeline before full synced audio replay". Both TranscriptTurn and
WorkspaceEvent already carried real created_at timestamps before this -
EvidenceDrawer.tsx's "no per-timestamp replay data exists yet" comment was
about the API never exposing them together, not the data not existing.

Covers orchestrator.get_round_timeline: merges both sources in chronological
order, and _workspace_event_summary builds an honest one-line summary per
event kind (no fabricated code/canvas content - WorkspaceEvent only ever
stored light metadata, never a full snapshot).

Same isolated-private-engine pattern as test_drills.py/test_prep_plans.py.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api import orchestrator
from apps.api.db import Base
from apps.api.models import LoopAttempt, RoundAttempt, TranscriptTurn, WorkspaceEvent

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)


def _bare_round(db, user_id: str) -> RoundAttempt:
    loop = LoopAttempt(user_id=user_id)
    db.add(loop)
    db.flush()
    round_ = RoundAttempt(
        loop_attempt_id=loop.id,
        user_id=user_id,
        round_type="coding",
        role_family="software_engineer",
        level="senior",
        domain="backend",
        company_profile="startup",
        duration_minutes=45,
        modality="text",
        scenario_id="s1",
        scenario_prompt="p",
        status="ACTIVE",
        phase="INTRO",
        coverage={},
        started_at=datetime.now(timezone.utc),
    )
    db.add(round_)
    db.commit()
    db.refresh(round_)
    return round_


def test_timeline_merges_turns_and_workspace_events_in_chronological_order():
    db = SessionLocal()
    try:
        round_ = _bare_round(db, "u1")
        t0 = datetime.now(timezone.utc)

        db.add(
            TranscriptTurn(
                round_id=round_.id,
                turn_index=0,
                speaker="interviewer",
                text="Let's start with the problem.",
                phase="INTRO",
                created_at=t0,
            )
        )
        db.add(
            WorkspaceEvent(
                round_id=round_.id,
                kind="code_change",
                payload={"code_language": "python", "code_length": 42},
                created_at=t0 + timedelta(seconds=30),
            )
        )
        db.add(
            WorkspaceEvent(
                round_id=round_.id,
                kind="test_result",
                payload={"test_results": [{"passed": True}, {"passed": False}, {"passed": True}]},
                created_at=t0 + timedelta(seconds=60),
            )
        )
        db.add(
            TranscriptTurn(
                round_id=round_.id,
                turn_index=1,
                speaker="candidate",
                text="I think I've got it.",
                phase="ACTIVE",
                created_at=t0 + timedelta(seconds=90),
            )
        )
        db.commit()

        timeline = orchestrator.get_round_timeline(db, round_.id)

        assert [item.kind for item in timeline] == [
            "turn:interviewer",
            "code_change",
            "test_result",
            "turn:candidate",
        ]
        # Strictly chronological.
        assert [item.created_at for item in timeline] == sorted(item.created_at for item in timeline)
        assert timeline[0].text == "Let's start with the problem."
        assert "python" in timeline[1].text
        assert timeline[2].text == "Tests: 2/3 passed"
        assert timeline[3].text == "I think I've got it."
    finally:
        db.close()


def test_timeline_is_empty_for_a_round_with_no_activity_yet():
    db = SessionLocal()
    try:
        round_ = _bare_round(db, "u2")
        assert orchestrator.get_round_timeline(db, round_.id) == []
    finally:
        db.close()


def test_canvas_and_run_event_summaries_are_human_readable():
    db = SessionLocal()
    try:
        round_ = _bare_round(db, "u3")
        db.add(
            WorkspaceEvent(
                round_id=round_.id,
                kind="run_attempt",
                payload={"language": "python", "code_length": 100},
            )
        )
        db.add(
            WorkspaceEvent(
                round_id=round_.id,
                kind="canvas_change",
                payload={"canvas_summary": "3 boxes, 2 arrows", "element_count": 5},
            )
        )
        db.commit()

        timeline = orchestrator.get_round_timeline(db, round_.id)
        texts = {item.kind: item.text for item in timeline}
        assert texts["run_attempt"] == "Ran python (100 chars)"
        assert texts["canvas_change"] == "Canvas updated - 5 elements (3 boxes, 2 arrows)"
    finally:
        db.close()
