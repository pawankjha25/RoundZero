"""
World-model persistence and API (specs/005-world-model-interviewer): the
orchestrator hooks (tracking after every turn, shadow vs live steering, catch-up
at submit), the report endpoints, the level-only-after-the-interview rule,
retries and the competency trend. Private SQLite engine + dependency overrides,
same pattern as test_admin_and_report.py. No API keys - the rule-based
extractor runs inline.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

for _k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(_k, None)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from apps.api import orchestrator, worldmodel_service  # noqa: E402
from apps.api.db import Base, get_db  # noqa: E402
from apps.api.deps import get_current_user  # noqa: E402
from apps.api.models import (  # noqa: E402
    LoopAttempt,
    RoundAttempt,
    TranscriptTurn,
    User,
    WMDecision,
    WMEvidence,
    WMProcessedTurn,
)
from apps.api.routes import world_model  # noqa: E402

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)

_app = FastAPI()
_app.include_router(world_model.router)
_app.include_router(world_model.trend_router)


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_app.dependency_overrides[get_db] = _override_get_db
client = TestClient(_app)

LONG = (
    "I would start by pinning down the success metric and the latency budget, then split the "
    "system into an ingestion path, a training pipeline and an online serving tier with a "
    "feature store in between, and I would size the serving tier from peak QPS and the model's "
    "memory footprint rather than from averages."
)


def _as_user(user_id: str):
    def _dep():
        with SessionLocal() as db:
            u = db.get(User, user_id)
            if u is None:
                u = User(id=user_id, email=f"{user_id}@example.com", name="Test")
                db.add(u)
                db.commit()
                db.refresh(u)
            return u

    _app.dependency_overrides[get_current_user] = _dep


def _round(db, user_id: str, status: str = "ACTIVE") -> RoundAttempt:
    loop = LoopAttempt(user_id=user_id)
    db.add(loop)
    db.flush()
    r = RoundAttempt(
        loop_attempt_id=loop.id, user_id=user_id, round_type="ml_system_design", role_family="ml_engineer",
        level="staff", domain="ml_infra", company_profile="generic", duration_minutes=45, modality="text",
        scenario_id="s1", scenario_prompt="Design an LLM serving platform.", status=status, phase="INTRO",
        coverage={}, started_at=datetime.now(timezone.utc),
    )
    db.add(r)
    db.flush()
    db.add(TranscriptTurn(round_id=r.id, turn_index=0, speaker="interviewer", text="Walk me through the architecture.",
                          phase="INTRO", competency_tags=["architecture", "framing"]))
    db.commit()
    db.refresh(r)
    return r


def test_post_message_tracks_the_answer_and_logs_a_shadow_decision(monkeypatch):
    monkeypatch.setenv("ROUNDZERO_WM_ADAPTIVE", "shadow")
    with SessionLocal() as db:
        r = _round(db, "u-track")
        orchestrator.post_message(db, r, LONG)
        assert db.query(WMProcessedTurn).filter_by(round_id=r.id).count() == 1
        assert db.query(WMEvidence).filter_by(round_id=r.id).count() >= 1
        decision = db.query(WMDecision).filter_by(round_id=r.id).one()
        assert decision.mode == "shadow" and decision.chosen_competency
        # shadow mode never steers the interviewer
        assert worldmodel_service.current_probe_hint(db, r) is None
        # idempotent
        assert worldmodel_service.catch_up(db, r.id) == 0


def test_live_mode_produces_a_probe_hint(monkeypatch):
    monkeypatch.setenv("ROUNDZERO_WM_ADAPTIVE", "live")
    with SessionLocal() as db:
        r = _round(db, "u-live")
        orchestrator.post_message(db, r, LONG)
        hint = worldmodel_service.current_probe_hint(db, r)
        assert hint and "Adaptive probing note" in hint


def test_adaptive_off_logs_no_decision(monkeypatch):
    monkeypatch.setenv("ROUNDZERO_WM_ADAPTIVE", "off")
    with SessionLocal() as db:
        r = _round(db, "u-off")
        orchestrator.post_message(db, r, LONG)
        assert db.query(WMDecision).filter_by(round_id=r.id).count() == 0


def test_world_model_disabled_does_nothing(monkeypatch):
    monkeypatch.setenv("ROUNDZERO_WM_ENABLED", "0")
    with SessionLocal() as db:
        r = _round(db, "u-disabled")
        orchestrator.post_message(db, r, LONG)
        assert db.query(WMProcessedTurn).filter_by(round_id=r.id).count() == 0


def test_level_is_hidden_until_the_interview_is_submitted():
    _as_user("u-api")
    with SessionLocal() as db:
        r = _round(db, "u-api")
        orchestrator.post_message(db, r, LONG)
        round_id = r.id
    assert client.get(f"/v1/rounds/{round_id}/world-model").status_code == 409

    with SessionLocal() as db:
        r = db.get(RoundAttempt, round_id)
        r.status = "EVALUATED"
        db.commit()
    res = client.get(f"/v1/rounds/{round_id}/world-model")
    assert res.status_code == 200
    body = res.json()
    assert body["answers_processed"] == body["answers_total"] == 1
    assert {c["competency"] for c in body["competencies"]} >= {"problem_framing", "ml_system_design"}
    assert body["flip_available"] is False
    assert all(len(c["path"]) == 1 for c in body["competencies"])


def test_other_users_cannot_read_a_round():
    _as_user("u-owner")
    with SessionLocal() as db:
        r = _round(db, "u-owner", status="EVALUATED")
        round_id = r.id
    _as_user("u-intruder")
    assert client.get(f"/v1/rounds/{round_id}/world-model").status_code == 404


def test_retry_endpoint_and_rewrites_need_a_key():
    _as_user("u-retry")
    with SessionLocal() as db:
        r = _round(db, "u-retry")
        orchestrator.post_message(db, r, "Short answer.")
        r.status = "EVALUATED"
        db.commit()
        round_id = r.id
    res = client.post(f"/v1/rounds/{round_id}/world-model/retries", json={"turn_index": 1, "text": LONG})
    assert res.status_code == 200
    body = res.json()
    assert body["turn_index"] == 1 and body["id"]
    assert client.get(f"/v1/rounds/{round_id}/world-model").json()["retries"][0]["retry_text"] == LONG
    bad = client.post(f"/v1/rounds/{round_id}/world-model/retries", json={"turn_index": 0, "text": "x"})
    assert bad.status_code == 422
    assert client.post(f"/v1/rounds/{round_id}/world-model/rewrites").status_code == 503


def test_competency_trend_lists_evaluated_rounds_oldest_first():
    _as_user("u-trend")
    with SessionLocal() as db:
        ids = []
        for _ in range(2):
            r = _round(db, "u-trend")
            orchestrator.post_message(db, r, LONG)
            r.status = "EVALUATED"
            db.commit()
            ids.append(r.id)
    res = client.get("/v1/report/competency-trend")
    assert res.status_code == 200
    assert [p["round_id"] for p in res.json()] == ids
    assert res.json()[0]["levels"]
