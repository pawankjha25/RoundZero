"""
Prep Plans - user-pitched feature (not from the P0 backlog): a candidate's
own self-curated prep plan (e.g. "Staff MLE prep"), organized into areas
each holding a list of practice questions they pick from deliberately
("what am I in the mood to practice today") instead of always getting a
randomly picked scenario via pick_scenario(). See apps/api/models.py's
PrepPlan/PrepPlanArea/PrepPlanQuestion docstrings for the full data model,
and orchestrator.py's "Prep Plans" section for the business logic - this
module is thin: resolve ownership, call the orchestrator, serialize.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from apps.api import orchestrator
from apps.api.db import get_db
from apps.api.deps import get_current_user
from apps.api.models import PrepPlan, PrepPlanArea, PrepPlanQuestion, User
from apps.api.routes.rounds import _round_out, _turn_out
from apps.api.schemas import (
    AddBankQuestionIn,
    AddCustomQuestionIn,
    BankScenarioOut,
    PrepPlanAreaIn,
    PrepPlanAreaOut,
    PrepPlanIn,
    PrepPlanOut,
    PrepPlanQuestionOut,
    RoundDetailOut,
    SuggestedQuestionOut,
    SuggestQuestionsOut,
)
from roundzero.prep_plan.suggest import SuggestedQuestion, scenario_id_of

router = APIRouter(prefix="/v1/prep-plans", tags=["prep-plans"])


def _get_owned_plan(db: DBSession, plan_id: str, user: User) -> PrepPlan:
    plan = orchestrator.get_owned_prep_plan(db, user.id, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prep plan not found")
    return plan


def _get_owned_area(db: DBSession, area_id: str, user: User) -> PrepPlanArea:
    area = orchestrator.get_owned_prep_plan_area(db, user.id, area_id)
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prep plan area not found")
    return area


def _question_out(db: DBSession, question: PrepPlanQuestion) -> PrepPlanQuestionOut:
    return PrepPlanQuestionOut(
        id=question.id,
        area_id=question.area_id,
        prompt=question.prompt,
        notes=question.notes,
        source=question.source,
        scenario_id=question.scenario_id,
        progress=orchestrator.question_progress(db, question.id),
    )


def _area_out(db: DBSession, area: PrepPlanArea, *, include_questions: bool) -> PrepPlanAreaOut:
    questions: list[PrepPlanQuestionOut] = []
    if include_questions:
        rows = (
            db.query(PrepPlanQuestion)
            .filter(PrepPlanQuestion.area_id == area.id)
            .order_by(PrepPlanQuestion.sort_order)
            .all()
        )
        questions = [_question_out(db, q) for q in rows]
    return PrepPlanAreaOut(
        id=area.id,
        plan_id=area.plan_id,
        round_type=area.round_type,
        label=area.label,
        sort_order=area.sort_order,
        questions=questions,
    )


def _plan_out(db: DBSession, plan: PrepPlan, *, include_areas: bool) -> PrepPlanOut:
    areas: list[PrepPlanAreaOut] = []
    if include_areas:
        rows = db.query(PrepPlanArea).filter(PrepPlanArea.plan_id == plan.id).order_by(PrepPlanArea.sort_order).all()
        areas = [_area_out(db, a, include_questions=True) for a in rows]
    return PrepPlanOut(
        id=plan.id,
        name=plan.name,
        role_family=plan.role_family,
        level=plan.level,
        domain=plan.domain,
        company_profile=plan.company_profile,
        duration_minutes=plan.duration_minutes,
        mode=plan.mode,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        areas=areas,
    )


@router.post("", response_model=PrepPlanOut)
def create_prep_plan(
    req: PrepPlanIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> PrepPlanOut:
    plan = orchestrator.create_prep_plan(db, user.id, req)
    return _plan_out(db, plan, include_areas=True)


@router.get("", response_model=list[PrepPlanOut])
def list_prep_plans(
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> list[PrepPlanOut]:
    # List cards only need plan-level fields (apps/web/app/prep-plans/page.tsx) -
    # areas/questions/progress are left out here to avoid N+1 progress lookups
    # for a page that doesn't render them; the detail page (GET /{plan_id})
    # fetches the full nested shape.
    plans = orchestrator.list_prep_plans(db, user.id)
    return [_plan_out(db, p, include_areas=False) for p in plans]


@router.get("/{plan_id}", response_model=PrepPlanOut)
def get_prep_plan(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> PrepPlanOut:
    plan = _get_owned_plan(db, plan_id, user)
    return _plan_out(db, plan, include_areas=True)


@router.patch("/{plan_id}", response_model=PrepPlanOut)
def update_prep_plan(
    plan_id: str,
    req: PrepPlanIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> PrepPlanOut:
    plan = _get_owned_plan(db, plan_id, user)
    plan = orchestrator.update_prep_plan(db, plan, req)
    return _plan_out(db, plan, include_areas=True)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prep_plan(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> None:
    plan = _get_owned_plan(db, plan_id, user)
    orchestrator.delete_prep_plan(db, plan)


@router.post("/{plan_id}/areas", response_model=PrepPlanAreaOut)
def add_prep_plan_area(
    plan_id: str,
    req: PrepPlanAreaIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> PrepPlanAreaOut:
    plan = _get_owned_plan(db, plan_id, user)
    try:
        area = orchestrator.add_prep_plan_area(db, plan, req)
    except orchestrator.RoundTypeNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _area_out(db, area, include_questions=True)


@router.delete("/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prep_plan_area(
    area_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> None:
    area = _get_owned_area(db, area_id, user)
    orchestrator.delete_prep_plan_area(db, area)


@router.get("/areas/{area_id}/bank-scenarios", response_model=list[BankScenarioOut])
def list_bank_scenarios(
    area_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> list[BankScenarioOut]:
    area = _get_owned_area(db, area_id, user)
    scenarios = orchestrator.list_bank_scenarios_for_area(db, area)
    return [
        BankScenarioOut(scenario_id=scenario_id_of(s), prompt=s["prompt"], title=s.get("title"))
        for s in scenarios
    ]


@router.post("/areas/{area_id}/questions/from-bank", response_model=PrepPlanQuestionOut)
def add_question_from_bank(
    area_id: str,
    req: AddBankQuestionIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> PrepPlanQuestionOut:
    area = _get_owned_area(db, area_id, user)
    try:
        question = orchestrator.add_prep_plan_question_from_bank(db, area, req.scenario_id)
    except orchestrator.BankScenarioNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _question_out(db, question)


@router.post("/areas/{area_id}/questions/custom", response_model=PrepPlanQuestionOut)
def add_custom_question(
    area_id: str,
    req: AddCustomQuestionIn,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> PrepPlanQuestionOut:
    area = _get_owned_area(db, area_id, user)
    try:
        question = orchestrator.add_custom_prep_plan_question(db, area, req)
    except orchestrator.CustomQuestionNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _question_out(db, question)


@router.post("/areas/{area_id}/suggest-questions", response_model=SuggestQuestionsOut)
def suggest_questions(
    area_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> SuggestQuestionsOut:
    """Preview only - nothing persisted. The candidate adds whichever
    suggestions they want via POST .../questions/from-bank (if the
    suggestion carries a scenario_id) or a dedicated add-suggested call -
    see add_suggested_question below."""
    area = _get_owned_area(db, area_id, user)
    suggestions = orchestrator.suggest_prep_plan_questions(db, area)
    return SuggestQuestionsOut(
        questions=[SuggestedQuestionOut(prompt=s.prompt, notes=s.notes, scenario_id=s.scenario_id) for s in suggestions]
    )


@router.post("/areas/{area_id}/questions/from-suggestion", response_model=PrepPlanQuestionOut)
def add_suggested_question(
    area_id: str,
    req: SuggestedQuestionOut,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> PrepPlanQuestionOut:
    """Adds one specific suggestion the candidate clicked "Add" on, verbatim
    as returned by POST .../suggest-questions (never re-derived) - see
    orchestrator.add_suggested_prep_plan_question."""
    area = _get_owned_area(db, area_id, user)
    suggestion = SuggestedQuestion(prompt=req.prompt, notes=req.notes, scenario_id=req.scenario_id)
    question = orchestrator.add_suggested_prep_plan_question(db, area, suggestion)
    return _question_out(db, question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prep_plan_question(
    question_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> None:
    question = orchestrator.get_owned_prep_plan_question(db, user.id, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prep plan question not found")
    orchestrator.delete_prep_plan_question(db, question)


@router.post("/questions/{question_id}/start", response_model=RoundDetailOut)
def start_round_from_question(
    question_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RoundDetailOut:
    """Click a question, start a round against exactly that scenario -
    returns the same RoundDetailOut shape POST /v1/rounds already returns,
    so the frontend enters the normal interview room unchanged."""
    try:
        round_, first_turn = orchestrator.start_round_from_plan_question(db, user.id, question_id)
    except orchestrator.PlanQuestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except orchestrator.InterviewerUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return RoundDetailOut(round=_round_out(round_), transcript=[_turn_out(first_turn)])
