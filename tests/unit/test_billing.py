"""
Stripe billing (apps/api/routes/billing.py) - Phase 2's one-time Pay-per-loop
Checkout flow. Covers: both routes degrade to 501 with no Stripe keys set
(never a broken/misleading response), checkout builds a session with the
right amount/metadata for a known pack and rejects an unknown one, the
webhook credits rounds on checkout.session.completed, is idempotent against
Stripe's at-least-once delivery (the same event id only credits once), and
rejects a bad signature. Never hits the real Stripe network - stripe.
checkout.Session.create and stripe.Webhook.construct_event are monkeypatched.

Same standalone-app + TestClient + private-SQLite-engine pattern as
test_feedback.py, for the same isolation reasons documented there.
"""
from __future__ import annotations

import json
import os
import tempfile

os.environ.setdefault("ADMIN_EMAILS", "")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import stripe  # noqa: E402

from apps.api.db import Base, get_db  # noqa: E402
from apps.api.deps import get_current_user  # noqa: E402
from apps.api.models import StripeWebhookEvent, User, UserEntitlement  # noqa: E402
from apps.api.routes import billing  # noqa: E402

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)

_app = FastAPI()
_app.include_router(billing.router)


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_app.dependency_overrides[get_db] = _override_get_db
client = TestClient(_app)


def _as_user(user_id: str, email: str | None = None, name: str = "Buyer"):
    # email defaults to one derived from user_id, not a shared literal -
    # users.email is unique now (2026-09-29 fix), and several tests in this
    # file each create their own throwaway user via this helper, so a fixed
    # default would collide across tests sharing the module-level engine.
    resolved_email = email or f"{user_id}@example.com"

    def _dep():
        db = SessionLocal()
        u = db.get(User, user_id)
        if u is None:
            u = User(id=user_id, email=resolved_email, name=name)
            db.add(u)
            db.commit()
            db.refresh(u)
        db.close()
        return u

    _app.dependency_overrides[get_current_user] = _dep


def _entitlement(user_id: str) -> UserEntitlement | None:
    db = SessionLocal()
    try:
        return db.query(UserEntitlement).filter(UserEntitlement.user_id == user_id).first()
    finally:
        db.close()


class _FakeSession:
    def __init__(self, url: str):
        self.url = url


def test_checkout_501s_when_stripe_is_not_configured(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    _as_user("buy-user-unconfigured")
    r = client.post("/v1/billing/checkout", json={"pack": "pack_4"})
    assert r.status_code == 501


def test_checkout_rejects_an_unknown_pack(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    _as_user("buy-user-badpack")
    r = client.post("/v1/billing/checkout", json={"pack": "not_a_real_pack"})
    assert r.status_code == 400


def test_checkout_creates_a_session_with_the_right_amount_and_metadata(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    captured = {}

    def _fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeSession(url="https://checkout.stripe.com/fake-session")

    monkeypatch.setattr(stripe.checkout.Session, "create", _fake_create)
    _as_user("buy-user-checkout", email="checkout@example.com")

    r = client.post("/v1/billing/checkout", json={"pack": "pack_12"})
    assert r.status_code == 200
    assert r.json()["checkout_url"] == "https://checkout.stripe.com/fake-session"

    assert captured["mode"] == "payment"
    assert captured["line_items"][0]["price_data"]["unit_amount"] == 8000
    assert captured["metadata"]["user_id"] == "buy-user-checkout"
    assert captured["metadata"]["rounds"] == "12"
    assert captured["success_url"].startswith("http://localhost:3000/upgrade")
    assert captured["client_reference_id"] == "buy-user-checkout"


def test_webhook_501s_when_webhook_secret_is_not_configured(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    r = client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"})
    assert r.status_code == 501


def test_webhook_rejects_a_bad_signature(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake")

    def _fake_construct_event(payload, sig_header, secret):
        raise stripe.error.SignatureVerificationError("bad sig", sig_header)

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(_fake_construct_event))
    r = client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "bad"})
    assert r.status_code == 400


def _fake_checkout_completed_event(event_id: str, user_id: str, rounds: int, customer: str | None = None):
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"user_id": user_id, "pack": "pack_4", "rounds": str(rounds)},
                "customer": customer,
            }
        },
    }


def test_webhook_credits_rounds_on_checkout_completed(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake")
    user_id = "buy-user-credited"
    db = SessionLocal()
    try:
        db.add(User(id=user_id, email="credited@example.com", name="Credited"))
        db.commit()
    finally:
        db.close()
    event = _fake_checkout_completed_event("evt_credit_1", user_id, 4, customer="cus_fake123")

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda payload, sig, secret: event))
    r = client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "ok"})
    assert r.status_code == 200

    row = _entitlement(user_id)
    assert row is not None
    assert row.rounds_included == 4
    assert row.cohort == "paid"
    assert row.plan == "payperloop"
    assert row.expires_at is None

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        assert user is not None and user.stripe_customer_id == "cus_fake123"
    finally:
        db.close()


def test_webhook_is_idempotent_against_duplicate_delivery(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake")
    user_id = "buy-user-duplicate"
    event = _fake_checkout_completed_event("evt_dup_1", user_id, 4)

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda payload, sig, secret: event))

    r1 = client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "ok"})
    r2 = client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "ok"})
    assert r1.status_code == 200
    assert r2.status_code == 200

    row = _entitlement(user_id)
    assert row.rounds_included == 4  # not 8 - the retry didn't double-credit

    db = SessionLocal()
    try:
        assert db.query(StripeWebhookEvent).filter(StripeWebhookEvent.id == "evt_dup_1").count() == 1
    finally:
        db.close()


def test_webhook_does_not_downgrade_an_existing_better_plan(monkeypatch):
    """credit_purchase's docstring: a subscriber (Phase 3, hypothetical here)
    buying a top-up pack keeps their subscription's plan name."""
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake")
    user_id = "buy-user-subscriber"
    db = SessionLocal()
    try:
        db.add(User(id=user_id, email="subscriber@example.com", name="Subscriber"))
        db.add(UserEntitlement(user_id=user_id, cohort="paid", plan="monthly", rounds_included=16))
        db.commit()
    finally:
        db.close()

    event = _fake_checkout_completed_event("evt_topup_1", user_id, 4)
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda payload, sig, secret: event))
    r = client.post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "ok"})
    assert r.status_code == 200

    row = _entitlement(user_id)
    assert row.plan == "monthly"  # unchanged
    assert row.rounds_included == 20  # 16 + 4
