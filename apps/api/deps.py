"""
Supabase JWT verification - replaces the Milestone 1 cookie-session auth
(apps.api.models.SessionToken is now dead - Supabase issues and manages
sessions, the backend only verifies them). Every request must carry
`Authorization: Bearer <supabase access token>`.

Verification is JWKS-based (SUPABASE_URL -> <url>/auth/v1/.well-known/jwks.json),
not a static HS256 shared secret: Supabase's newer projects sign access tokens
with an asymmetric key (ES256 by default) and only publish the *public* half at
the JWKS endpoint, so the backend never holds a signing secret at all. This
also means a project that later rotates its signing key (Supabase dashboard ->
Settings -> JWT Keys) needs no backend redeploy - PyJWKClient picks the right
public key by the token's `kid` header automatically. (Older Supabase projects
that still use the legacy HS256 shared secret are not supported here; migrate
via the Supabase dashboard's JWT Keys page if you're on one.)

On first verification for a given Supabase user, upserts a local "shadow
profile" row (apps.api.models.User) keyed by the token's `sub` claim, so
RoundAttempt/etc. still have a local user_id to join against without
duplicating Supabase's own auth.users table.

Admin access (get_current_admin below) is a plain email allowlist read from
ADMIN_EMAILS (comma-separated, case-insensitive) - not a DB column. There's
no user-management UI to safely flip a stored is_admin flag yet, and an
allowlist is config (.env), not a hardcoded value or a manual DB edit: adding
or removing an admin is a redeploy-free env var change.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from apps.api.db import get_db
from apps.api.models import (
    TESTER_ROUNDS_INCLUDED,
    TRIAL_ROUNDS_INCLUDED,
    TRIAL_WINDOW_DAYS,
    UNSELECTED_PLAN,
    User,
    UserEntitlement,
)

_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_URL is not set on the server - see .env.example",
        )
    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(jwks_url, cache_keys=True)


def _decode(token: str) -> dict:
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session") from exc


def _tester_emails() -> set[str]:
    raw = os.environ.get("TESTER_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_tester_email(email: str) -> bool:
    """Dogfooding/pilot-user allowlist, same shape as is_admin_email below
    (comma-separated TESTER_EMAILS env var, case-insensitive) - config, not a
    DB column, so inviting a new tester is a redeploy-free env var change."""
    return bool(email) and email.lower() in _tester_emails()


def _ensure_entitlement(db: DBSession, user: User) -> None:
    """Auto-grant a UserEntitlement row the first time we ever see this user
    - called from get_current_user for every request, but a no-op once the
    row exists (cheap indexed lookup, and this only ever runs at creation -
    an existing row, however it got its plan, is never touched again here).
    This also backfills any user created before this feature shipped, the
    first time they make any authenticated request after deploy - no
    migration/backfill script needed. cohort/plan are decided once, here,
    from TESTER_EMAILS/ADMIN_EMAILS at creation time; never re-derived later
    even if those env vars change afterward.

    Three paths (see UserEntitlement's docstring, "Subscribe gate" paragraph,
    for the reasoning):
      - Tester allowlist -> the full 8-round dogfooder grant, immediately.
      - Admin allowlist -> the normal free-trial grant, immediately - admins
        are Pawan's own curated accounts, not organic signups, so they skip
        the Subscribe gate below.
      - Everyone else (a real self-signup) -> UNSELECTED_PLAN, 0 rounds.
        Nothing to practice with until they explicitly pick a plan via
        POST /v1/auth/subscribe (orchestrator.select_plan) - see apps/web's
        /upgrade page."""
    existing = db.query(UserEntitlement).filter(UserEntitlement.user_id == user.id).first()
    if existing is not None:
        return
    now = datetime.now(timezone.utc)
    if is_tester_email(user.email):
        entitlement = UserEntitlement(
            user_id=user.id,
            cohort="tester",
            plan="none",
            rounds_included=TESTER_ROUNDS_INCLUDED,
            current_period_start=now,
            expires_at=None,
        )
    elif is_admin_email(user.email):
        entitlement = UserEntitlement(
            user_id=user.id,
            cohort="normal",
            plan="none",
            rounds_included=TRIAL_ROUNDS_INCLUDED,
            current_period_start=now,
            expires_at=now + timedelta(days=TRIAL_WINDOW_DAYS),
        )
    else:
        entitlement = UserEntitlement(
            user_id=user.id,
            cohort="normal",
            plan=UNSELECTED_PLAN,
            rounds_included=0,
            current_period_start=now,
            expires_at=None,
        )
    db.add(entitlement)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent first-time requests for the same brand-new user (same
        # React Strict Mode double-invoke this guards against for the User
        # row itself, right below) - the loser just rolls back, a row now
        # exists either way.
        db.rollback()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: DBSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")

    claims = _decode(credentials.credentials)
    user_id = claims["sub"]
    email = claims.get("email", "")
    metadata = claims.get("user_metadata") or {}
    name = metadata.get("full_name") or metadata.get("name") or email

    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=email, name=name)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            # Two different collisions land here, both non-fatal:
            #  1. Same brand-new Supabase user racing with itself (Next.js
            #     dev mode's React Strict Mode double-invokes effects, so
            #     the dashboard's me() call fires twice on mount) - a
            #     primary-key collision, the winner's row is exactly what
            #     we would have written.
            #  2. A different Supabase auth.users id sharing this email -
            #     e.g. Google OAuth vs the email magic link, which Supabase
            #     doesn't automatically treat as the same identity - hits
            #     email's UNIQUE constraint (models.py::User). This is the
            #     case that models.py's docstring flags: rather than 500ing
            #     this person's login, treat it as the same person's other
            #     sign-in method and reuse their existing row/history.
            # Either way, some row already represents this person - read it
            # back instead of failing the request.
            db.rollback()
            user = db.get(User, user_id) or db.query(User).filter(User.email == email).first()
            if user is None:
                raise
        else:
            db.refresh(user)
    elif user.email != email or (name and user.name != name):
        user.email = email
        user.name = name or user.name
        try:
            db.commit()
        except IntegrityError:
            # This Supabase identity's email changed to one that's already
            # taken by a different local User row (email's UNIQUE
            # constraint) - an edge case, but one that must not 500 an
            # otherwise-valid request. Keep this row's previous email
            # rather than crash; the name change (if any) is lost too since
            # it's the same commit, but that's a display nit, not a broken
            # login.
            db.rollback()
            db.refresh(user)
        else:
            db.refresh(user)
    _ensure_entitlement(db, user)
    return user


def _admin_emails() -> set[str]:
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_admin_email(email: str) -> bool:
    return bool(email) and email.lower() in _admin_emails()


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not is_admin_email(user.email):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
