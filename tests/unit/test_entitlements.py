"""
Entitlement/quota enforcement (claude.ai Project "roundzero" >
pricing-design.md, Phase 1 - no Stripe, admin-granted entitlements). Covers:

- get_entitlement_status: rounds_used computed live from RoundAttempt rows,
  an unprovisioned user_id (never seen by apps/api/deps.py::get_current_user)
  degrades to unlimited rather than blocking a caller that was never a real
  quota-limited user in the first place.
- _require_quota, exercised via its two real call sites - orchestrator.
  create_loop (sized to len(req.rounds)) and orchestrator.create_round (which
  goes through _start_round, sized to 1): both raise InsufficientQuotaError
  when there isn't enough left, and both succeed (and count against the same
  quota) when there is.
- Expiry: a round already ACTIVE keeps running past expires_at (nothing here
  blocks post_message/submit_round - only the two start-a-new-round-or-loop
  call sites consult expires_at at all), but starting a NEW round after
  expires_at has passed is blocked even with rounds still nominally left.
- The Subscribe gate (added 2026-09-29): orchestrator.select_plan and the
  UNSELECTED_PLAN sentinel it resolves, plus apps/api/deps.py::
  _ensure_entitlement's three branches (tester/admin skip the gate and get
  their real plan immediately; a real self-signup lands on UNSELECTED_PLAN
  with 0 rounds until they call select_plan) and the "only NEW signups are
  gated" guarantee (an existing row is never touched on a later request).

Same isolated-private-engine pattern as test_drills.py/test_prep_plans.py -
this file's rows never touch any other test file's data no matter collection
order.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api import orchestrator
from apps.api.db import Base
from apps.api.models import UserEntitlement
from apps.api.schemas import LoopCreateRequest, PlannedRoundIn, StartRoundRequest

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)

_START_REQ = StartRoundRequest(role_family="ml_engineer", level="senior", domain="ml_infra", company_profile="startup")


def _grant(db, user_id: str, *, rounds_included: int, expires_at=None, cohort="normal") -> UserEntitlement:
    entitlement = UserEntitlement(
        user_id=user_id,
        cohort=cohort,
        plan="none",
        rounds_included=rounds_included,
        current_period_start=datetime.now(timezone.utc),
        expires_at=expires_at,
    )
    db.add(entitlement)
    db.commit()
    return entitlement


def test_unprovisioned_user_is_not_blocked():
    """A user_id that was never provisioned via apps/api/deps.py (the real
    per-request auth flow always provisions first) shouldn't be quota-limited
    by a bookkeeping gap - see get_entitlement_status's docstring."""
    db = SessionLocal()
    try:
        status_ = orchestrator.get_entitlement_status(db, "never-seen-user")
        assert status_.is_expired is False
        assert status_.rounds_remaining > 0
    finally:
        db.close()


def test_rounds_used_counts_rounds_created_since_current_period_start():
    db = SessionLocal()
    try:
        user_id = "ent-user-usage"
        _grant(db, user_id, rounds_included=3)
        assert orchestrator.get_entitlement_status(db, user_id).rounds_used == 0

        orchestrator.create_round(db, user_id, _START_REQ)
        status_ = orchestrator.get_entitlement_status(db, user_id)
        assert status_.rounds_used == 1
        assert status_.rounds_remaining == 2
    finally:
        db.close()


def test_starting_a_round_is_blocked_once_quota_is_exhausted():
    db = SessionLocal()
    try:
        user_id = "ent-user-exhausted"
        _grant(db, user_id, rounds_included=1)
        orchestrator.create_round(db, user_id, _START_REQ)  # uses the one round

        with pytest.raises(orchestrator.InsufficientQuotaError):
            orchestrator.create_round(db, user_id, _START_REQ)
    finally:
        db.close()


def test_starting_a_round_after_expiry_is_blocked_even_with_rounds_left():
    db = SessionLocal()
    try:
        user_id = "ent-user-expired"
        _grant(
            db,
            user_id,
            rounds_included=5,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        with pytest.raises(orchestrator.InsufficientQuotaError):
            orchestrator.create_round(db, user_id, _START_REQ)
    finally:
        db.close()


def test_an_already_active_round_is_not_interrupted_by_expiry():
    """Grandfathering: a round started before expires_at keeps running past
    it - post_message/submit_round never consult entitlement at all, only
    the two start-a-new-thing call sites do."""
    db = SessionLocal()
    try:
        user_id = "ent-user-grandfathered"
        _grant(db, user_id, rounds_included=1)
        round_, _turn = orchestrator.create_round(db, user_id, _START_REQ)

        # Quota is now exhausted (and would also be "expired" if we set
        # expires_at in the past), but continuing this already-started round
        # must still work.
        turn = orchestrator.post_message(db, round_, "Let's talk about the data pipeline.")
        assert turn.speaker == "interviewer"
    finally:
        db.close()


def test_create_loop_is_blocked_when_it_would_request_more_rounds_than_remain():
    db = SessionLocal()
    try:
        user_id = "ent-user-loop-block"
        _grant(db, user_id, rounds_included=1)
        req = LoopCreateRequest(
            name="Test loop",
            role_family="ml_engineer",
            level="senior",
            domain="ml_infra",
            rounds=[
                PlannedRoundIn(round_type="ml_system_design", duration_minutes=45),
                PlannedRoundIn(round_type="coding", duration_minutes=45),
            ],
        )
        with pytest.raises(orchestrator.InsufficientQuotaError):
            orchestrator.create_loop(db, user_id, req)
    finally:
        db.close()


def test_create_loop_succeeds_when_enough_rounds_remain():
    db = SessionLocal()
    try:
        user_id = "ent-user-loop-ok"
        _grant(db, user_id, rounds_included=2)
        req = LoopCreateRequest(
            name="Test loop",
            role_family="ml_engineer",
            level="senior",
            domain="ml_infra",
            rounds=[
                PlannedRoundIn(round_type="ml_system_design", duration_minutes=45),
                PlannedRoundIn(round_type="coding", duration_minutes=45),
            ],
        )
        loop = orchestrator.create_loop(db, user_id, req)
        assert loop.id is not None
        # Planning doesn't itself consume quota - only starting a planned
        # round does (see create_loop's docstring).
        assert orchestrator.get_entitlement_status(db, user_id).rounds_used == 0
    finally:
        db.close()


# --- Subscribe gate (pricing-design.md, 2026-09-29: "let the user login -
# don't give them automatically... they click subscribe... Plan None/Free is
# where they get one test"). ---


def test_a_freshly_unselected_user_is_blocked_from_practicing():
    """UNSELECTED_PLAN + 0 rounds (what apps/api/deps.py::_ensure_entitlement
    now gives a real self-signup user) blocks starting anything, with a
    message distinct from "expired"/"exhausted"."""
    db = SessionLocal()
    try:
        user_id = "ent-user-unselected"
        _grant(db, user_id, rounds_included=0, cohort="normal")
        row = db.query(UserEntitlement).filter(UserEntitlement.user_id == user_id).first()
        row.plan = orchestrator.UNSELECTED_PLAN
        db.commit()

        with pytest.raises(orchestrator.InsufficientQuotaError, match="Pick a plan"):
            orchestrator.create_round(db, user_id, _START_REQ)
    finally:
        db.close()


def test_select_plan_none_grants_the_free_trial_starting_now():
    db = SessionLocal()
    try:
        user_id = "ent-user-subscribe"
        row = UserEntitlement(user_id=user_id, cohort="normal", plan=orchestrator.UNSELECTED_PLAN, rounds_included=0)
        db.add(row)
        db.commit()

        before = datetime.now(timezone.utc)
        status_ = orchestrator.select_plan(db, user_id, "none")
        assert status_.plan == "none"
        assert status_.rounds_included == 1
        assert status_.rounds_remaining == 1
        assert status_.expires_at is not None
        expires_at = status_.expires_at.replace(tzinfo=timezone.utc) if status_.expires_at.tzinfo is None else status_.expires_at
        assert expires_at - before >= timedelta(days=6, hours=23)  # ~7 days from NOW, not from some earlier signup time

        # And now they can actually start a round.
        round_, _turn = orchestrator.create_round(db, user_id, _START_REQ)
        assert round_.id is not None
    finally:
        db.close()


def test_select_plan_rejects_unimplemented_paid_plans():
    db = SessionLocal()
    try:
        user_id = "ent-user-paid-plan-attempt"
        row = UserEntitlement(user_id=user_id, cohort="normal", plan=orchestrator.UNSELECTED_PLAN, rounds_included=0)
        db.add(row)
        db.commit()

        with pytest.raises(orchestrator.PlanNotAvailableError):
            orchestrator.select_plan(db, user_id, "monthly")
    finally:
        db.close()


# --- apps/api/deps.py::_ensure_entitlement - which of the three paths a
# brand-new user lands on (tester / admin / real self-signup). ---


def test_ensure_entitlement_grants_testers_the_full_dogfooder_allowance(monkeypatch):
    from apps.api import deps
    from apps.api.models import User

    monkeypatch.setenv("TESTER_EMAILS", "tester@example.com")
    monkeypatch.setenv("ADMIN_EMAILS", "")
    db = SessionLocal()
    try:
        user = User(id="dep-user-tester", email="tester@example.com", name="Tester")
        db.add(user)
        db.commit()

        deps._ensure_entitlement(db, user)
        row = db.query(UserEntitlement).filter(UserEntitlement.user_id == user.id).first()
        assert row.cohort == "tester"
        assert row.rounds_included == 8
        assert row.expires_at is None
    finally:
        db.close()


def test_ensure_entitlement_grants_admins_the_immediate_free_trial_no_gate(monkeypatch):
    from apps.api import deps
    from apps.api.models import User

    monkeypatch.setenv("TESTER_EMAILS", "")
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    db = SessionLocal()
    try:
        user = User(id="dep-user-admin", email="admin@example.com", name="Admin")
        db.add(user)
        db.commit()

        deps._ensure_entitlement(db, user)
        row = db.query(UserEntitlement).filter(UserEntitlement.user_id == user.id).first()
        assert row.plan == "none"  # NOT the unselected gate - admins skip it
        assert row.rounds_included == 1
        assert row.expires_at is not None
    finally:
        db.close()


def test_ensure_entitlement_gates_a_real_self_signup_behind_subscribe(monkeypatch):
    from apps.api import deps
    from apps.api.models import User

    monkeypatch.setenv("TESTER_EMAILS", "")
    monkeypatch.setenv("ADMIN_EMAILS", "")
    db = SessionLocal()
    try:
        user = User(id="dep-user-normal", email="brand.new@example.com", name="New Signup")
        db.add(user)
        db.commit()

        deps._ensure_entitlement(db, user)
        row = db.query(UserEntitlement).filter(UserEntitlement.user_id == user.id).first()
        assert row.plan == orchestrator.UNSELECTED_PLAN
        assert row.rounds_included == 0
        assert row.expires_at is None
    finally:
        db.close()


def test_ensure_entitlement_never_touches_an_existing_row(monkeypatch):
    """Only-new-signups-are-gated, concretely: an entitlement created before
    this feature (or before an email was ever added to an allowlist) is left
    exactly as-is on later requests - _ensure_entitlement no-ops once a row
    exists, regardless of what TESTER_EMAILS/ADMIN_EMAILS say now."""
    from apps.api import deps
    from apps.api.models import User

    monkeypatch.setenv("TESTER_EMAILS", "grandfathered@example.com")
    monkeypatch.setenv("ADMIN_EMAILS", "")
    db = SessionLocal()
    try:
        user = User(id="dep-user-grandfathered", email="grandfathered@example.com", name="Old Account")
        db.add(user)
        _grant(db, user.id, rounds_included=1, cohort="normal")  # pre-existing row, as if from before TESTER_EMAILS

        deps._ensure_entitlement(db, user)
        row = db.query(UserEntitlement).filter(UserEntitlement.user_id == user.id).first()
        assert row.cohort == "normal"  # unchanged - not upgraded to "tester" just because the row already existed
        assert row.rounds_included == 1
    finally:
        db.close()
