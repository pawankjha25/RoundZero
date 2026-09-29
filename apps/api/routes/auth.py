"""
Auth - Supabase issues and manages sessions client-side (Google OAuth + email
magic link, apps/web/app/(auth)/login/page.tsx); this backend never sees a
password and never issues its own session. /me verifies the caller's Supabase
access token (apps.api.deps.get_current_user) and returns the local shadow
profile, upserted from the token's claims on first sight, plus a live
entitlement summary (see apps/api/models.py::UserEntitlement and
orchestrator.get_entitlement_status) so the frontend's quota pill
(apps/web/components/AppShell.tsx) can render off this one call rather than
a separate network round trip.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from apps.api import orchestrator
from apps.api.db import get_db
from apps.api.deps import get_current_user, is_admin_email
from apps.api.models import User
from sqlalchemy.orm import Session as DBSession

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class EntitlementOut(BaseModel):
    cohort: str
    plan: str
    rounds_included: int
    rounds_used: int
    rounds_remaining: int
    current_period_start: datetime
    expires_at: datetime | None
    is_expired: bool


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    is_admin: bool
    entitlement: EntitlementOut


class SubscribeIn(BaseModel):
    # Only "none" (the free plan) actually does anything right now - see
    # orchestrator.select_plan's docstring. Not a Literal["none"] because the
    # frontend's Subscribe page sends the plan the user clicked even for the
    # disabled paid cards (shouldn't be clickable, but this way a stale UI
    # or a direct API call gets a real 400 with a clear message instead of a
    # generic validation error).
    plan: str


def _entitlement_out(status_: orchestrator.EntitlementStatus) -> EntitlementOut:
    return EntitlementOut(
        cohort=status_.cohort,
        plan=status_.plan,
        rounds_included=status_.rounds_included,
        rounds_used=status_.rounds_used,
        rounds_remaining=status_.rounds_remaining,
        current_period_start=status_.current_period_start,
        expires_at=status_.expires_at,
        is_expired=status_.is_expired,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> UserOut:
    # is_admin is derived from ADMIN_EMAILS (apps.api.deps), not a User column
    # - computed fresh on every /me call so revoking access is instant (no
    # stale flag to clean up), not just at login time.
    status_ = orchestrator.get_entitlement_status(db, user.id)
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        is_admin=is_admin_email(user.email),
        entitlement=_entitlement_out(status_),
    )


@router.post("/subscribe", response_model=EntitlementOut)
def subscribe(
    payload: SubscribeIn, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)
) -> EntitlementOut:
    """The Subscribe step (apps/web's /upgrade page) - see
    orchestrator.select_plan's docstring. Picking "none" is what actually
    grants a self-signup user their free round; every paid plan 400s for
    now since Stripe isn't connected (pricing-design.md Phase 2/3)."""
    try:
        status_ = orchestrator.select_plan(db, user.id, payload.plan)
    except orchestrator.PlanNotAvailableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _entitlement_out(status_)
