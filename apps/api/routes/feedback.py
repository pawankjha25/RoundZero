"""
Feedback/issue/advice capture for the small-pilot test-user period. Any
authenticated user can submit via the floating widget mounted globally in
apps/web/app/layout.tsx (deliberately outside AppShell, so it's reachable
even mid-interview - see that file's comment). The admin-only listing (with
the submitter's email and name joined in) lives in apps/api/routes/admin.py
alongside the rest of the admin surface, not here - this router only ever
needs get_current_user, never get_current_admin.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from apps.api.db import get_db
from apps.api.deps import get_current_user
from apps.api.models import Feedback, User

router = APIRouter(prefix="/v1/feedback", tags=["feedback"])

_KINDS = {"feedback", "issue", "advice"}


class FeedbackIn(BaseModel):
    kind: str = "feedback"
    message: str
    page_path: str | None = None


class FeedbackOut(BaseModel):
    id: str
    kind: str


@router.post("", response_model=FeedbackOut)
def submit_feedback(
    payload: FeedbackIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> FeedbackOut:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Message can't be empty")
    kind = payload.kind if payload.kind in _KINDS else "feedback"
    row = Feedback(
        user_id=user.id,
        kind=kind,
        message=message,
        page_path=payload.page_path,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return FeedbackOut(id=row.id, kind=row.kind)
