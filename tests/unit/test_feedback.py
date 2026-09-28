"""
Feedback capture (apps/api/routes/feedback.py) and its admin-only listing
(apps/api/routes/admin.py's GET /v1/admin/feedback) - the small-pilot
"report an issue/feedback/advice" widget. Covers: any authenticated user can
submit, an empty message is rejected, an unknown `kind` falls back to
"feedback" rather than 500ing, a non-admin is blocked from the listing, and
the listing joins in the submitter's email/name (the two fields the user
explicitly asked to see) newest-first.

Same standalone-app + private-SQLite-engine pattern as
test_admin_and_report.py, for the same reasons documented there.
"""
from __future__ import annotations

import os
import tempfile

os.environ["ADMIN_EMAILS"] = "admin@example.com"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from apps.api.db import Base, get_db  # noqa: E402
from apps.api.deps import get_current_user  # noqa: E402
from apps.api.models import User  # noqa: E402
from apps.api.routes import admin, feedback  # noqa: E402

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)

_app = FastAPI()
_app.include_router(feedback.router)
_app.include_router(admin.router)


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_app.dependency_overrides[get_db] = _override_get_db
client = TestClient(_app)


def _as_user(user_id: str, email: str, name: str = "Test User"):
    def _dep():
        db = SessionLocal()
        u = db.get(User, user_id)
        if u is None:
            u = User(id=user_id, email=email, name=name)
            db.add(u)
            db.commit()
            db.refresh(u)
        db.close()
        return u

    _app.dependency_overrides[get_current_user] = _dep


def test_authenticated_user_can_submit_feedback():
    _as_user("candidate-1", "candidate@example.com", "Cathy Candidate")
    r = client.post("/v1/feedback", json={"kind": "issue", "message": "The timer looked stuck.", "page_path": "/interview/abc"})
    assert r.status_code == 200
    assert r.json()["kind"] == "issue"


def test_empty_message_is_rejected():
    _as_user("candidate-1", "candidate@example.com")
    r = client.post("/v1/feedback", json={"kind": "advice", "message": "   "})
    assert r.status_code == 400


def test_unknown_kind_falls_back_to_feedback_instead_of_500():
    _as_user("candidate-1", "candidate@example.com")
    r = client.post("/v1/feedback", json={"kind": "not-a-real-kind", "message": "hello"})
    assert r.status_code == 200
    assert r.json()["kind"] == "feedback"


def test_non_admin_is_blocked_from_the_feedback_listing():
    _as_user("candidate-1", "candidate@example.com")
    assert client.get("/v1/admin/feedback").status_code == 403


def test_admin_listing_includes_submitter_email_and_name_newest_first():
    _as_user("dana-1", "dana@example.com", "Dana Doe")
    client.post("/v1/feedback", json={"kind": "feedback", "message": "First one."})
    client.post("/v1/feedback", json={"kind": "issue", "message": "Second one, a bit later."})

    _as_user("admin-1", "admin@example.com", "Admin")
    r = client.get("/v1/admin/feedback")
    assert r.status_code == 200
    rows = r.json()
    mine = [row for row in rows if row["user_email"] == "dana@example.com"]
    assert len(mine) == 2
    assert mine[0]["message"] == "Second one, a bit later."  # newest first
    assert mine[0]["user_name"] == "Dana Doe"
    assert mine[1]["message"] == "First one."
