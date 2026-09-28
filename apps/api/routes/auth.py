"""
Auth - Supabase issues and manages sessions client-side (Google OAuth + email
magic link, apps/web/app/(auth)/login/page.tsx); this backend never sees a
password and never issues its own session. /me verifies the caller's Supabase
access token (apps.api.deps.get_current_user) and returns the local shadow
profile, upserted from the token's claims on first sight.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.deps import get_current_user, is_admin_email
from apps.api.models import User

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    is_admin: bool


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    # is_admin is derived from ADMIN_EMAILS (apps.api.deps), not a User column
    # - computed fresh on every /me call so revoking access is instant (no
    # stale flag to clean up), not just at login time.
    return UserOut(id=user.id, email=user.email, name=user.name, is_admin=is_admin_email(user.email))
