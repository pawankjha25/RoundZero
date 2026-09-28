"""
World-model API (specs/005-world-model-interviewer).

- GET  /v1/rounds/{id}/world-model           - path map, diagnosis, rewrites, retries
- POST /v1/rounds/{id}/world-model/rewrites  - generate flip rewrites (hypothetical)
- POST /v1/rounds/{id}/world-model/retries   - score a real retried answer
- GET  /v1/report/competency-trend           - final level per competency across rounds

The level estimate is only ever exposed after the interview (decided
2026-09-28), so every per-round endpoint refuses a round that is still ACTIVE
or WRAP_UP.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from apps.api import worldmodel_service
from apps.api.db import get_db
from apps.api.deps import get_current_user
from apps.api.models import RoundAttempt, User
from roundzero.worldmodel.models import FlipRewrite, RetryResult, WorldModelReport
from roundzero.worldmodel.retry import NotAnAnswerTurnError

router = APIRouter(prefix="/v1/rounds", tags=["world-model"])
trend_router = APIRouter(prefix="/v1/report", tags=["world-model"])

_LIVE_STATUSES = ("CREATED", "ACTIVE", "WRAP_UP")


def _get_finished_round(db: DBSession, round_id: str, user: User) -> RoundAttempt:
    round_ = db.get(RoundAttempt, round_id)
    if round_ is None or round_.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if round_.status in _LIVE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The level read is only available after the interview is submitted.",
        )
    return round_


@router.get("/{round_id}/world-model", response_model=WorldModelReport)
def get_world_model(
    round_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)
) -> WorldModelReport:
    round_ = _get_finished_round(db, round_id, user)
    worldmodel_service.catch_up(db, round_.id)
    return worldmodel_service.build_report(db, round_)


@router.post("/{round_id}/world-model/rewrites", response_model=list[FlipRewrite])
def create_rewrites(
    round_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)
) -> list[FlipRewrite]:
    round_ = _get_finished_round(db, round_id, user)
    try:
        return worldmodel_service.create_rewrites(db, round_)
    except worldmodel_service.FlipUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


class RetryIn(BaseModel):
    turn_index: int
    text: str = Field(min_length=1, max_length=6000)


@router.post("/{round_id}/world-model/retries", response_model=RetryResult)
def create_retry(
    round_id: str,
    payload: RetryIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RetryResult:
    round_ = _get_finished_round(db, round_id, user)
    try:
        return worldmodel_service.create_retry(db, round_, user.id, payload.turn_index, payload.text.strip())
    except NotAnAnswerTurnError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


class TrendLevelOut(BaseModel):
    competency: str
    label: str
    mean: float
    level: str | None
    abstained: bool


class TrendPointOut(BaseModel):
    round_id: str
    round_type: str
    created_at: datetime | None
    levels: list[TrendLevelOut]


@trend_router.get("/competency-trend", response_model=list[TrendPointOut])
def get_competency_trend(
    user: User = Depends(get_current_user), db: DBSession = Depends(get_db)
) -> list[TrendPointOut]:
    return [TrendPointOut.model_validate(p) for p in worldmodel_service.competency_trend(db, user.id)]
