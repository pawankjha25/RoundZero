"""
Loop Planner API (specs/002-full-loop-platform P0.1): create a loop with one
or more planned rounds up front, list a user's loops (each with its planned
rounds' current state), and start one specific planned round when the
candidate is ready for it. See apps/api/models.py::PlannedRound and
apps/api/orchestrator.py::create_loop/start_planned_round for the shape and
why starting is a separate step from planning.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from apps.api import orchestrator
from apps.api.db import get_db
from apps.api.deps import get_current_user
from apps.api.models import LoopAttempt, PlannedRound, RoundAttempt, User
from apps.api.schemas import (
    CommitteeReportOut,
    LoopCreateRequest,
    LoopNameSuggestionOut,
    LoopOut,
    PlannedRoundOut,
    RoundDetailOut,
    TurnOut,
)
from apps.api.routes.rounds import _round_out, _turn_out

router = APIRouter(prefix="/v1/loops", tags=["loops"])


def _get_owned_loop(db: DBSession, loop_id: str, user: User) -> LoopAttempt:
    loop = db.get(LoopAttempt, loop_id)
    if loop is None or loop.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loop not found")
    return loop


def _planned_round_out(db: DBSession, planned: PlannedRound) -> PlannedRoundOut:
    started = None
    if planned.round_attempt_id is not None:
        round_ = db.get(RoundAttempt, planned.round_attempt_id)
        if round_ is not None:
            evaluation = orchestrator.get_report(db, round_.id)
            started = orchestrator.history_item_out(round_, evaluation)
    return PlannedRoundOut(
        id=planned.id,
        round_type=planned.round_type,
        role_family=planned.role_family,
        level=planned.level,
        domain=planned.domain,
        company_profile=planned.company_profile,
        duration_minutes=planned.duration_minutes,
        modality=planned.modality,
        sort_order=planned.sort_order,
        startable=(planned.round_attempt_id is None and planned.round_type in orchestrator.REAL_ROUND_TYPES),
        started=started,
    )


def _loop_out(db: DBSession, loop: LoopAttempt) -> LoopOut:
    planned_rounds = orchestrator.list_planned_rounds(db, loop.id)
    return LoopOut(
        id=loop.id,
        name=loop.name or "Untitled loop",
        created_at=loop.created_at,
        rounds=[_planned_round_out(db, p) for p in planned_rounds],
    )


@router.post("", response_model=LoopOut)
def create_loop(
    payload: LoopCreateRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> LoopOut:
    if not payload.rounds:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Pick at least one round for this loop.")
    try:
        loop = orchestrator.create_loop(db, user.id, payload)
    except orchestrator.InsufficientQuotaError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc
    return _loop_out(db, loop)


@router.get("", response_model=list[LoopOut])
def list_loops(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> list[LoopOut]:
    loops = orchestrator.list_loops(db, user.id)
    return [_loop_out(db, loop) for loop in loops]


# Static path - must be registered before GET /{loop_id} below, or FastAPI
# would try to match "suggested-name" as a loop_id path param instead.
@router.get("/suggested-name", response_model=LoopNameSuggestionOut)
def suggested_name(
    role_family: str,
    level: str,
    company_profile: str = "generic",
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> LoopNameSuggestionOut:
    return LoopNameSuggestionOut(name=orchestrator.suggest_loop_name(db, user.id, role_family, level, company_profile))


@router.get("/{loop_id}", response_model=LoopOut)
def get_loop(loop_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> LoopOut:
    loop = _get_owned_loop(db, loop_id, user)
    return _loop_out(db, loop)


@router.delete("/{loop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loop(loop_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> None:
    loop = _get_owned_loop(db, loop_id, user)
    orchestrator.delete_loop(db, loop)


@router.post("/{loop_id}/rounds/{planned_round_id}/start", response_model=RoundDetailOut)
def start_planned_round(
    loop_id: str,
    planned_round_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RoundDetailOut:
    loop = _get_owned_loop(db, loop_id, user)
    planned = db.get(PlannedRound, planned_round_id)
    if planned is None or planned.loop_attempt_id != loop.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Planned round not found in this loop")

    try:
        round_, first_turn = orchestrator.start_planned_round(db, user.id, planned_round_id)
    except orchestrator.PlannedRoundNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except orchestrator.PlannedRoundAlreadyStartedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except orchestrator.RoundTypeNotAvailableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except orchestrator.InsufficientQuotaError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc
    except orchestrator.InterviewerUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return RoundDetailOut(round=_round_out(round_), transcript=[_turn_out(first_turn)])


def _committee_out(report_tuple: tuple) -> CommitteeReportOut:
    report, rounds_included, generated_at = report_tuple
    return CommitteeReportOut(
        overall_readiness_pct=report.overall_readiness_pct,
        overall_hire_signal=report.overall_hire_signal,
        confidence=report.confidence,
        headline=report.headline,
        strengths=report.strengths,
        concerns=report.concerns,
        level_signal=report.level_signal,
        key_evidence=report.key_evidence,
        rounds_included=rounds_included,
        generated_at=generated_at,
    )


@router.get("/{loop_id}/committee", response_model=CommitteeReportOut)
def get_committee(loop_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> CommitteeReportOut:
    """Read-only (specs/002-full-loop-platform P0.6) - never triggers the LLM
    call. 404 covers "not eligible yet" and "eligible but not generated/stale"
    alike (see orchestrator.get_committee_report's docstring) - the frontend's
    next move is the same either way: POST to (re)generate."""
    loop = _get_owned_loop(db, loop_id, user)
    result = orchestrator.get_committee_report(db, loop)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No committee verdict available yet for this loop")
    return _committee_out(result)


@router.post("/{loop_id}/committee", response_model=CommitteeReportOut)
def generate_committee(loop_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> CommitteeReportOut:
    """Builds-or-returns-cached-fresh (specs/002-full-loop-platform P0.6) - see
    orchestrator.generate_committee_report's docstring for the caching rule."""
    loop = _get_owned_loop(db, loop_id, user)
    try:
        result = orchestrator.generate_committee_report(db, loop)
    except orchestrator.CommitteeNotReadyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except orchestrator.CommitteeUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return _committee_out(result)
