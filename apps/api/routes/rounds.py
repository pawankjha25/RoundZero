"""
Rounds API - Milestone 1 (start/message/status) through Milestone 3 (report,
history). Simplified vs. milestone-1.md's literal API surface (separate
check-in/events/submit/status endpoints backed by a general event log): here
POST /v1/rounds does setup+check-in+first-turn in one call, and
POST /v1/rounds/{id}/message does append-candidate-turn+call-interviewer+append-
interviewer-turn in one call. Same runtime flow (milestone-1.md step by step),
fewer round trips - reasonable for a single-server BFF; splitting further is
free to do later if a real multi-client/reconnect story needs it (milestone-1.md
Decision 2 already scopes full reconnect out to Milestone 4 anyway).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from apps.api import orchestrator
from apps.api.db import get_db
from apps.api.deps import get_current_user
from apps.api.models import RoundAttempt, RoundWorkspaceState, User, WorkspaceEvent
from apps.api.schemas import (
    CanvasSaveRequest,
    CodeSaveRequest,
    DrillRequest,
    HistoryItemOut,
    MessageRequest,
    RoundComparisonOut,
    RoundDetailOut,
    RoundEvaluationOut,
    RoundOut,
    RunCodeRequest,
    RunCodeResult,
    StartRoundRequest,
    TimelineEventOut,
    TurnOut,
    VoiceTokenOut,
    WorkspaceStateOut,
)
from roundzero.coding.execution import CodeTestCase, get_execution_provider
from roundzero.coding.feedback import generate_code_feedback
from roundzero.realtime.tokens import (
    RealtimeNotConfiguredError,
    is_configured as realtime_is_configured,
    mint_livekit_token,
    room_name_for_round,
    get_livekit_url,
)

router = APIRouter(prefix="/v1/rounds", tags=["rounds"])


def _get_owned_round(db: DBSession, round_id: str, user: User) -> RoundAttempt:
    round_ = db.get(RoundAttempt, round_id)
    if round_ is None or round_.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    return round_


def _round_out(round_: RoundAttempt) -> RoundOut:
    return RoundOut(
        id=round_.id,
        loop_attempt_id=round_.loop_attempt_id,
        round_type=round_.round_type,
        modality=round_.modality,
        role_family=round_.role_family,
        level=round_.level,
        domain=round_.domain,
        company_profile=round_.company_profile,
        duration_minutes=round_.duration_minutes,
        status=round_.status,
        phase=round_.phase,
        coverage=round_.coverage,
        time_remaining_sec=orchestrator.time_remaining_sec(round_),
        created_at=round_.created_at,
        submitted_at=round_.submitted_at,
        scenario_prompt=round_.scenario_prompt,
        scenario_meta=round_.scenario_meta or {},
    )


def _turn_out(turn) -> TurnOut:
    return TurnOut(
        speaker=turn.speaker, text=turn.text, phase=turn.phase, turn_index=turn.turn_index, created_at=turn.created_at
    )


def _workspace_state_out(round_id: str, state: RoundWorkspaceState | None) -> WorkspaceStateOut:
    if state is None:
        return WorkspaceStateOut(round_id=round_id)
    return WorkspaceStateOut(
        round_id=state.round_id,
        code_language=state.code_language,
        code_text=state.code_text,
        canvas_scene=state.canvas_scene,
        canvas_summary=state.canvas_summary,
        updated_at=state.updated_at,
    )


def _get_or_create_workspace_state(db: DBSession, round_id: str) -> RoundWorkspaceState:
    state = db.get(RoundWorkspaceState, round_id)
    if state is None:
        state = RoundWorkspaceState(round_id=round_id)
        db.add(state)
        db.flush()
    return state


@router.post("", response_model=RoundDetailOut)
def start_round(
    payload: StartRoundRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RoundDetailOut:
    try:
        round_, first_turn = orchestrator.create_round(db, user.id, payload)
    except orchestrator.RoundTypeNotAvailableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except orchestrator.InterviewerUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return RoundDetailOut(round=_round_out(round_), transcript=[_turn_out(first_turn)])


@router.get("", response_model=list[HistoryItemOut])
def list_rounds(user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> list[HistoryItemOut]:
    rounds = (
        db.query(RoundAttempt)
        .filter(RoundAttempt.user_id == user.id)
        .order_by(RoundAttempt.created_at.desc())
        .all()
    )
    return [orchestrator.history_item_out(r, orchestrator.get_report(db, r.id)) for r in rounds]


# Registered before /{round_id} on purpose - FastAPI/Starlette match routes in
# registration order, and /{round_id} would otherwise swallow "compare" as a
# round_id value and 404 (no round literally named "compare").
@router.get("/compare", response_model=RoundComparisonOut)
def compare_rounds(
    round_id_a: str,
    round_id_b: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RoundComparisonOut:
    if round_id_a == round_id_b:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Pick two different rounds to compare.")
    round_a = _get_owned_round(db, round_id_a, user)
    round_b = _get_owned_round(db, round_id_b, user)
    if round_a.round_type != round_b.round_type:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Can only compare two rounds of the same round type right now.",
        )
    comparison = orchestrator.compare_rounds(db, round_a, round_b)
    if comparison is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Both rounds need to be submitted and evaluated before they can be compared.",
        )
    return comparison


@router.get("/{round_id}", response_model=RoundDetailOut)
def get_round(round_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> RoundDetailOut:
    round_ = _get_owned_round(db, round_id, user)
    turns = orchestrator.load_transcript(db, round_.id)
    return RoundDetailOut(round=_round_out(round_), transcript=[_turn_out(t) for t in turns])


class MessageResponseOut(BaseModel):
    round: RoundOut
    turn: TurnOut


@router.post("/{round_id}/message", response_model=MessageResponseOut)
def post_message(
    round_id: str,
    payload: MessageRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> MessageResponseOut:
    round_ = _get_owned_round(db, round_id, user)
    if round_.status not in ("ACTIVE", "WRAP_UP"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Round is {round_.status}, not accepting messages")
    try:
        turn = orchestrator.post_message(db, round_, payload.text)
    except orchestrator.InterviewerUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    db.refresh(round_)
    return MessageResponseOut(round=_round_out(round_), turn=_turn_out(turn))


@router.post("/{round_id}/submit", response_model=RoundEvaluationOut)
def submit_round(round_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> RoundEvaluationOut:
    round_ = _get_owned_round(db, round_id, user)
    try:
        return orchestrator.submit_round(db, round_)
    except orchestrator.EvaluationUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/{round_id}/report", response_model=RoundEvaluationOut)
def get_report(round_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> RoundEvaluationOut:
    round_ = _get_owned_round(db, round_id, user)
    report = orchestrator.get_report(db, round_.id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round has not been evaluated yet")
    return report


@router.get("/{round_id}/timeline", response_model=list[TimelineEventOut])
def get_timeline(round_id: str, user: User = Depends(get_current_user), db: DBSession = Depends(get_db)) -> list[TimelineEventOut]:
    """Interview Replay - chronological transcript + workspace-event timeline
    for a round (see orchestrator.get_round_timeline). Available for a round
    in any status, same as get_round, not just evaluated ones."""
    round_ = _get_owned_round(db, round_id, user)
    return orchestrator.get_round_timeline(db, round_.id)


@router.post("/{round_id}/drill", response_model=RoundDetailOut)
def start_drill(
    round_id: str,
    payload: DrillRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RoundDetailOut:
    """"Practice this weakness" - starts a new round biased toward one item
    from this (already-evaluated) round's improvement plan. Returns the same
    RoundDetailOut shape POST /v1/rounds already returns, so the frontend
    enters the normal interview room unchanged."""
    source_round = _get_owned_round(db, round_id, user)
    try:
        round_, first_turn = orchestrator.start_drill_round(db, user.id, source_round, payload.priority)
    except orchestrator.DrillSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except orchestrator.InterviewerUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return RoundDetailOut(round=_round_out(round_), transcript=[_turn_out(first_turn)])



# --- Workspace (Coding + System Design panels) -----------------------------
# Reuses the same ownership check (_get_owned_round) as every other round
# endpoint. Kept as their own small endpoints rather than folded into
# get_round/post_message, since the workspace panel autosaves independently of
# the chat turn loop (debounced client-side, not on every keystroke).


@router.get("/{round_id}/workspace", response_model=WorkspaceStateOut)
def get_workspace(
    round_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> WorkspaceStateOut:
    round_ = _get_owned_round(db, round_id, user)
    state = db.get(RoundWorkspaceState, round_.id)
    return _workspace_state_out(round_.id, state)


@router.put("/{round_id}/workspace/code", response_model=WorkspaceStateOut)
def save_code(
    round_id: str,
    payload: CodeSaveRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> WorkspaceStateOut:
    round_ = _get_owned_round(db, round_id, user)
    state = _get_or_create_workspace_state(db, round_.id)
    state.code_language = payload.code_language
    state.code_text = payload.code_text
    db.add(
        WorkspaceEvent(
            round_id=round_.id,
            kind="code_change",
            payload={"code_language": payload.code_language, "code_length": len(payload.code_text)},
        )
    )
    db.commit()
    db.refresh(state)
    return _workspace_state_out(round_.id, state)


@router.put("/{round_id}/workspace/canvas", response_model=WorkspaceStateOut)
def save_canvas(
    round_id: str,
    payload: CanvasSaveRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> WorkspaceStateOut:
    round_ = _get_owned_round(db, round_id, user)
    state = _get_or_create_workspace_state(db, round_.id)
    state.canvas_scene = payload.canvas_scene
    state.canvas_summary = payload.canvas_summary
    db.add(
        WorkspaceEvent(
            round_id=round_.id,
            kind="canvas_change",
            payload={"canvas_summary": payload.canvas_summary, "element_count": len(payload.canvas_scene)},
        )
    )
    db.commit()
    db.refresh(state)
    return _workspace_state_out(round_.id, state)


@router.post("/{round_id}/workspace/run", response_model=RunCodeResult)
def run_code(
    round_id: str,
    payload: RunCodeRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> RunCodeResult:
    round_ = _get_owned_round(db, round_id, user)
    provider = get_execution_provider()
    result = provider.run(
        language=payload.language,
        code=payload.code,
        test_cases=[CodeTestCase(**tc.model_dump()) for tc in payload.test_cases],
        entry_point=payload.entry_point,
    )
    try:
        # Best-effort: an LLM hiccup should never break the Run button itself -
        # the mechanical test results above are already valid on their own.
        result.feedback = generate_code_feedback(
            orchestrator.get_gateway(),
            language=payload.language,
            code=payload.code,
            executed=result.executed,
            test_results=result.test_results,
        )
    except Exception:
        pass
    db.add(
        WorkspaceEvent(
            round_id=round_.id,
            kind="run_attempt",
            payload={"language": payload.language, "code_length": len(payload.code)},
        )
    )
    db.add(
        WorkspaceEvent(
            round_id=round_.id,
            kind="test_result",
            payload={"test_results": [r.model_dump(mode="json") for r in result.test_results]},
        )
    )
    db.commit()
    return result


# Voice mode (Milestone 4, src/roundzero/realtime/). Orthogonal to the
# round-type routing above: gated on RoundAttempt.modality, set once at
# Setup time (StartRoundRequest.mode) and never changed mid-round. Minting a
# token here does not start the interview logic - the separate LiveKit
# Agents worker process (src/roundzero/realtime/agent.py) does that once the
# candidate actually joins the room; this endpoint only proves the candidate
# owns the round and hands them a scoped room-join credential.
@router.get("/{round_id}/voice/token", response_model=VoiceTokenOut)
def get_voice_token(
    round_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> VoiceTokenOut:
    round_ = _get_owned_round(db, round_id, user)
    if round_.modality == "text":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Voice mode wasn't enabled for this round - it was started as text-only.",
        )
    if not realtime_is_configured():
        # Graceful degradation to text (milestone-4.md runtime-flow step 7) -
        # never a hard failure the candidate can't route around.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice mode isn't configured on this server right now - continue by text.",
        )
    room_name = room_name_for_round(round_.id)
    try:
        token = mint_livekit_token(room_name=room_name, identity=user.id)
        url = get_livekit_url()
    except RealtimeNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return VoiceTokenOut(url=url, token=token, room=room_name)
