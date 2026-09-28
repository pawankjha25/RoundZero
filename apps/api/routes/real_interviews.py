"""
Real Interview Experience + Outcome Capture (specs/002-full-loop-platform
P0.11/P0.12). A candidate's own log of interviews they actually went through
at real companies - entirely separate from every other route module here,
which is all about simulated rounds. See apps/api/orchestrator.py's
create_real_interview_experience/real_interview_prediction docstrings for
the data model and the "prediction computed live, never stored" design.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from apps.api import orchestrator
from apps.api.db import get_db
from apps.api.deps import get_current_user
from apps.api.models import RealInterviewExperience, RealInterviewOutcome, User
from apps.api.schemas import (
    RealInterviewExperienceIn,
    RealInterviewExperienceOut,
    RealInterviewOutcomeIn,
    RealInterviewOutcomeOut,
    StructuredExperienceOut,
    StructureRequestIn,
)

router = APIRouter(prefix="/v1/real-interviews", tags=["real-interviews"])


def _get_owned_experience(db: DBSession, experience_id: str, user: User) -> RealInterviewExperience:
    experience = orchestrator.get_owned_real_interview_experience(db, user.id, experience_id)
    if experience is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Real interview not found")
    return experience


def _experience_out(db: DBSession, experience: RealInterviewExperience) -> RealInterviewExperienceOut:
    outcome_row = db.get(RealInterviewOutcome, experience.id)
    outcome = (
        RealInterviewOutcomeOut(
            status=outcome_row.status,
            stage=outcome_row.stage,
            target_level=outcome_row.target_level,
            offered_level=outcome_row.offered_level,
            notes=outcome_row.notes,
            updated_at=outcome_row.updated_at,
        )
        if outcome_row is not None
        else None
    )
    prediction = orchestrator.real_interview_prediction(db, experience)
    return RealInterviewExperienceOut(
        id=experience.id,
        company=experience.company,
        role_family=experience.role_family,
        level=experience.level,
        domain=experience.domain,
        interview_date=experience.interview_date,
        linked_loop_attempt_id=experience.linked_loop_attempt_id,
        rounds=experience.rounds,
        notes=experience.notes,
        self_assessment=experience.self_assessment,
        visibility=experience.visibility,
        created_at=experience.created_at,
        updated_at=experience.updated_at,
        outcome=outcome,
        prediction=prediction,
    )


@router.post("", response_model=RealInterviewExperienceOut)
def create_real_interview(
    req: RealInterviewExperienceIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RealInterviewExperienceOut:
    try:
        experience = orchestrator.create_real_interview_experience(db, user.id, req)
    except orchestrator.LinkedLoopNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _experience_out(db, experience)


@router.get("", response_model=list[RealInterviewExperienceOut])
def list_real_interviews(
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> list[RealInterviewExperienceOut]:
    experiences = orchestrator.list_real_interview_experiences(db, user.id)
    return [_experience_out(db, e) for e in experiences]


@router.get("/{experience_id}", response_model=RealInterviewExperienceOut)
def get_real_interview(
    experience_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RealInterviewExperienceOut:
    experience = _get_owned_experience(db, experience_id, user)
    return _experience_out(db, experience)


@router.patch("/{experience_id}", response_model=RealInterviewExperienceOut)
def update_real_interview(
    experience_id: str,
    req: RealInterviewExperienceIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RealInterviewExperienceOut:
    experience = _get_owned_experience(db, experience_id, user)
    try:
        experience = orchestrator.update_real_interview_experience(db, experience, req)
    except orchestrator.LinkedLoopNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _experience_out(db, experience)


@router.delete("/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_real_interview(
    experience_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> None:
    experience = _get_owned_experience(db, experience_id, user)
    orchestrator.delete_real_interview_experience(db, experience)


@router.post("/{experience_id}/outcome", response_model=RealInterviewExperienceOut)
def add_real_interview_outcome(
    experience_id: str,
    req: RealInterviewOutcomeIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RealInterviewExperienceOut:
    experience = _get_owned_experience(db, experience_id, user)
    orchestrator.upsert_real_interview_outcome(db, experience, req)
    return _experience_out(db, experience)


@router.post("/structure", response_model=StructuredExperienceOut)
def structure_real_interview(
    req: StructureRequestIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> StructuredExperienceOut:
    """Preview only - nothing persisted. The candidate reviews/edits this
    draft client-side; only POST /v1/real-interviews (or PATCH) actually
    saves anything, per this module's own docstring."""
    structured = orchestrator.structure_real_interview_text(req.raw_text, req.hints)
    return StructuredExperienceOut(
        rounds=[r.model_dump() for r in structured.rounds],
        self_assessment=structured.self_assessment,
    )
