"""
Candidate profile - PRD section 19's CandidateProfile (docs/PRD.md line 327),
narrowed to what /profile actually asks the candidate for today. Captures who
the candidate is and what they're aiming for (current role, target role,
experience, objective, and - for future use - a LinkedIn URL), independent of
any single round's Setup choices. One row per user, upserted in place.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from apps.api.db import get_db
from apps.api.deps import get_current_user
from apps.api.models import CandidateProfile, User
from apps.api.schemas import ProfileOut, ProfileUpdateRequest

router = APIRouter(prefix="/v1/profile", tags=["profile"])


def _profile_out(profile: CandidateProfile | None) -> ProfileOut:
    if profile is None:
        return ProfileOut()
    return ProfileOut(
        current_role=profile.current_role,
        target_role=profile.target_role,
        years_experience=profile.years_experience,
        experience_summary=profile.experience_summary,
        objective=profile.objective,
        linkedin_url=profile.linkedin_url,
        updated_at=profile.updated_at,
    )


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> ProfileOut:
    return _profile_out(db.get(CandidateProfile, user.id))


@router.put("", response_model=ProfileOut)
def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> ProfileOut:
    profile = db.get(CandidateProfile, user.id)
    if profile is None:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
    profile.current_role = payload.current_role
    profile.target_role = payload.target_role
    profile.years_experience = payload.years_experience
    profile.experience_summary = payload.experience_summary
    profile.objective = payload.objective
    profile.linkedin_url = payload.linkedin_url
    db.commit()
    db.refresh(profile)
    return _profile_out(profile)
