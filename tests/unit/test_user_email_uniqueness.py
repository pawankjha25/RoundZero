"""
users.email uniqueness (added 2026-09-29, after a real duplicate showed up in
dev: Google sign-in and the email magic link minted two different Supabase
auth.users ids for the same address, so get_current_user's old id-only
upsert created two separate local User rows for one person - two separate
entitlements, two separate round histories).

Covers the two things that change together here:
- models.py::User.email now has a UNIQUE constraint (SQLite - the index name
  matches apps/api/migrations/0007_users_email_unique.py).
- apps/api/deps.py::get_current_user handles the resulting IntegrityError by
  reusing the existing row (looked up by email) instead of 500ing - the
  behavior change models.py's docstring promises for two different Supabase
  identities sharing an email.

Calls get_current_user directly (not via HTTP/TestClient) with a
monkeypatched apps.api.deps._decode, since every other test file's
_as_user()-style helper stubs out get_current_user entirely via
dependency_overrides and so never actually exercises its body - this file
is the one place that does.

Same isolated-private-engine pattern as test_entitlements.py - this file's
rows never touch any other test file's data no matter collection order.
"""
from __future__ import annotations

import tempfile

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from apps.api import deps
from apps.api.db import Base
from apps.api.models import User

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _fake_decode_for(claims_by_token: dict[str, dict]):
    def _decode(token: str) -> dict:
        return claims_by_token[token]

    return _decode


def test_two_different_supabase_ids_sharing_an_email_collapse_to_one_user_row(monkeypatch):
    claims_by_token = {
        "token-google": {"sub": "supabase-id-google", "email": "pawan@example.com", "user_metadata": {"full_name": "Pawan"}},
        "token-magic-link": {"sub": "supabase-id-magiclink", "email": "pawan@example.com", "user_metadata": {}},
    }
    monkeypatch.setattr(deps, "_decode", _fake_decode_for(claims_by_token))

    db = SessionLocal()
    try:
        first = deps.get_current_user(credentials=_creds("token-google"), db=db)
        assert first.id == "supabase-id-google"
        assert first.email == "pawan@example.com"

        # A second, different Supabase identity for the same email must not
        # 500 - it should resolve to the same underlying row rather than
        # violating the unique constraint.
        second = deps.get_current_user(credentials=_creds("token-magic-link"), db=db)
        assert second.email == "pawan@example.com"
        assert second.id == first.id  # reused the existing row, not a new one

        rows = db.query(User).filter(User.email == "pawan@example.com").all()
        assert len(rows) == 1
    finally:
        db.close()


def test_email_column_rejects_a_raw_duplicate_insert():
    db = SessionLocal()
    try:
        db.add(User(id="dupe-a", email="dupe@example.com", name="A"))
        db.commit()

        db.add(User(id="dupe-b", email="dupe@example.com", name="B"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_changing_email_to_one_already_taken_does_not_500(monkeypatch):
    """The rarer edge case: an existing user's token email changes (Supabase
    side) to an address some other local row already owns. get_current_user
    must keep serving this request (with the old email) rather than crash."""
    db = SessionLocal()
    try:
        db.add(User(id="owner-of-taken-email", email="taken@example.com", name="Owner"))
        db.add(User(id="user-whose-email-changes", email="original@example.com", name="Changer"))
        db.commit()
    finally:
        db.close()

    claims_by_token = {
        "token-changed": {"sub": "user-whose-email-changes", "email": "taken@example.com", "user_metadata": {}},
    }
    monkeypatch.setattr(deps, "_decode", _fake_decode_for(claims_by_token))

    db = SessionLocal()
    try:
        result = deps.get_current_user(credentials=_creds("token-changed"), db=db)
        assert result.id == "user-whose-email-changes"
        # Kept its original email rather than crashing on the collision.
        assert result.email == "original@example.com"
    finally:
        db.close()
