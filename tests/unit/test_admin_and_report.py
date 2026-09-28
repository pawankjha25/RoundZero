"""
Admin-only management routes (apps/api/routes/admin.py) and the cross-loop
/report summary (apps/api/routes/report.py) - both new for the "admin view +
report tab" pass. Covers: ADMIN_EMAILS enforcement (both directions), the
generic option-list CRUD actually round-tripping through GET /v1/config/
options (proving admin edits are what candidates see, not a parallel copy),
round-type enable/disable, study-resource CRUD, settings, and the report
summary's weakest-dimension ranking + matching resource lookup.

Deliberately builds a standalone FastAPI app around just the routers under
test (config/admin/report), not apps.api.main - importing apps.api.main
inside a test process is unsafe: its module-level load_dotenv() call would
leak real GEMINI_API_KEY/OPENAI_API_KEY/ANTHROPIC_API_KEY values from the
repo's .env into every test file collected after this one in the same
pytest process, and apps.api.orchestrator.get_gateway()/get_evaluator() read
those fresh from os.environ - other test files that create rounds without
explicitly monkeypatching them would start hitting the real Gemini/OpenAI
APIs instead of the mocks they were written against.

Also uses its own private SQLite engine + a get_db dependency override
rather than the "set DATABASE_URL before importing apps.api.db" pattern
older tests in this directory use (test_orchestrator_interviewer_
unavailable.py, test_round_comparison.py) - apps.api.db.engine/SessionLocal
are module-level singletons configured once at the FIRST import of
apps.api.db anywhere in the pytest process, so whichever test file pytest
collects first "wins" that DATABASE_URL for every other file too. Overriding
get_db per-app sidesteps that race entirely: this file's tables live in
their own throwaway SQLite file no matter what any other test file does or
which order pytest collects things in.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

os.environ["ADMIN_EMAILS"] = "admin@example.com, Second.Admin@Example.com"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from apps.api.db import Base, get_db  # noqa: E402
from apps.api.deps import get_current_user  # noqa: E402
from apps.api.models import (  # noqa: E402
    EvaluationRecord,
    LoopAttempt,
    RoundAttempt,
    StudyResource,
    User,
)
from apps.api.routes import admin, config, report  # noqa: E402
from apps.api.seed import seed_defaults  # noqa: E402

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)

with SessionLocal() as _seed_db:
    seed_defaults(_seed_db)

_app = FastAPI()
_app.include_router(config.router)
_app.include_router(admin.router)
_app.include_router(report.router)


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_app.dependency_overrides[get_db] = _override_get_db
client = TestClient(_app)


def _as_user(user_id: str, email: str):
    def _dep():
        db = SessionLocal()
        u = db.get(User, user_id)
        if u is None:
            u = User(id=user_id, email=email, name="Test")
            db.add(u)
            db.commit()
            db.refresh(u)
        db.close()
        return u

    _app.dependency_overrides[get_current_user] = _dep


def test_non_admin_is_blocked_from_every_admin_route():
    _as_user("candidate-1", "candidate@example.com")
    assert client.get("/v1/admin/options/companies").status_code == 403
    assert client.get("/v1/admin/durations").status_code == 403
    assert client.get("/v1/admin/round-types").status_code == 403
    assert client.get("/v1/admin/study-resources").status_code == 403
    assert client.get("/v1/admin/settings").status_code == 403


def test_admin_allowlist_is_case_insensitive():
    _as_user("admin-1", "Admin@Example.com")
    assert client.get("/v1/admin/options/companies").status_code == 200


def test_admin_option_edits_are_what_the_public_endpoint_returns():
    _as_user("admin-1", "admin@example.com")
    r = client.post("/v1/admin/options/companies", json={"value": "faang", "label": "FAANG", "sort_order": 3})
    assert r.status_code == 200

    r = client.get("/v1/config/options")
    companies = {o["value"]: o["label"] for o in r.json()["companies"]}
    assert companies["faang"] == "FAANG"

    r = client.put("/v1/admin/options/companies/faang", json={"label": "Big Tech (FAANG)"})
    assert r.status_code == 200
    assert r.json()["label"] == "Big Tech (FAANG)"

    r = client.delete("/v1/admin/options/companies/faang")
    assert r.status_code == 204
    r = client.get("/v1/config/options")
    assert "faang" not in {o["value"] for o in r.json()["companies"]}


def test_unknown_option_kind_is_a_404_not_a_500():
    _as_user("admin-1", "admin@example.com")
    assert client.get("/v1/admin/options/not-a-real-kind").status_code == 404


def test_round_type_enable_disable_round_trips_to_public_options():
    # hiring_manager, not backend_system_design - backend_system_design (like
    # coding and ml_depth before it) now defaults to enabled=True since it has
    # a real interviewer (apps/api/seed.py, 2026-09-05: backend_system_design,
    # technical_leadership, and xfn all shipped real interviewers that day),
    # so it no longer exercises the False->True transition this test is
    # actually about. hiring_manager has no real interviewer yet and is the
    # only round type still defaulting to False - same disabled-by-default
    # round type this test always meant to flip, just a different one now
    # that the list of "coming soon" round types shrank.
    _as_user("admin-1", "admin@example.com")
    r = client.get("/v1/config/options")
    round_type = next(rt for rt in r.json()["round_types"] if rt["value"] == "hiring_manager")
    assert round_type["enabled"] is False

    r = client.put("/v1/admin/round-types/hiring_manager", json={"enabled": True})
    assert r.status_code == 200 and r.json()["enabled"] is True

    r = client.get("/v1/config/options")
    round_type = next(rt for rt in r.json()["round_types"] if rt["value"] == "hiring_manager")
    assert round_type["enabled"] is True


def test_study_resource_crud():
    _as_user("admin-1", "admin@example.com")
    r = client.post(
        "/v1/admin/study-resources",
        json={"dimension": "reliability", "title": "SRE Book", "kind": "book", "note": "solid"},
    )
    assert r.status_code == 200
    resource_id = r.json()["id"]

    r = client.get("/v1/admin/study-resources")
    assert any(x["id"] == resource_id for x in r.json())

    r = client.put(f"/v1/admin/study-resources/{resource_id}", json={"title": "SRE Book (2nd ed.)"})
    assert r.json()["title"] == "SRE Book (2nd ed.)"

    r = client.delete(f"/v1/admin/study-resources/{resource_id}")
    assert r.status_code == 204
    r = client.get("/v1/admin/study-resources")
    assert not any(x["id"] == resource_id for x in r.json())


def test_settings_reject_unknown_keys_and_round_trip_known_ones():
    _as_user("admin-1", "admin@example.com")
    assert client.put("/v1/admin/settings/not-a-real-setting", json={"value": "x"}).status_code == 404

    r = client.put("/v1/admin/settings/consultancy_booking_url", json={"value": "https://cal.com/pawan"})
    assert r.status_code == 200 and r.json()["value"] == "https://cal.com/pawan"

    r = client.get("/v1/admin/settings")
    setting = next(s for s in r.json() if s["key"] == "consultancy_booking_url")
    assert setting["value"] == "https://cal.com/pawan"


def test_report_summary_ranks_weakest_dimensions_and_attaches_matching_resources():
    _as_user("admin-1", "admin@example.com")
    client.post(
        "/v1/admin/study-resources",
        json={"dimension": "reliability", "title": "Reliability primer", "kind": "link", "url": "https://example.com"},
    )

    db = SessionLocal()
    loop = LoopAttempt(user_id="candidate-2")
    db.add(loop)
    db.flush()
    round_ = RoundAttempt(
        loop_attempt_id=loop.id,
        user_id="candidate-2",
        role_family="ml_engineer",
        level="senior",
        domain="ml_infra",
        company_profile="startup",
        duration_minutes=45,
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
    db.add(
        EvaluationRecord(
            round_id=round_.id,
            dimension_scores=[
                {
                    "dimension": "reliability",
                    "label": "Reliability",
                    "weight": 0.1,
                    "score": 1,
                    "evidence_narrative": "x",
                    "evidence": [],
                },
                {
                    "dimension": "framing",
                    "label": "Framing",
                    "weight": 0.1,
                    "score": 4,
                    "evidence_narrative": "y",
                    "evidence": [],
                },
            ],
            readiness_pct=45,
            hire_signal="LEAN NO HIRE",
            primary_concern="x",
            strengths=[],
            weaknesses=[],
            improvement_plan=[],
        )
    )
    round_id = round_.id
    db.commit()
    db.close()

    _as_user("candidate-2", "candidate2@example.com")
    r = client.get("/v1/report/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_loops"] == 1
    assert body["evaluated_rounds"] == 1
    assert body["avg_readiness_pct"] == 45
    assert body["latest_hire_signal"] == "LEAN NO HIRE"
    # reliability (score 1) must rank weaker than framing (score 4).
    assert body["weakest_dimensions"][0]["dimension"] == "reliability"
    assert any(res["dimension"] == "reliability" for res in body["suggested_resources"])
    assert len(body["loops"]) == 1
    assert body["loops"][0]["id"] == round_id


def test_report_summary_with_no_history_is_empty_not_an_error():
    _as_user("candidate-3", "candidate3@example.com")
    r = client.get("/v1/report/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_loops"] == 0
    assert body["avg_readiness_pct"] is None
    assert body["weakest_dimensions"] == []
    assert body["loops"] == []
