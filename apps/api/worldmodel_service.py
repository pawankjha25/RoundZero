"""
World-model persistence + orchestration glue (specs/005-world-model-interviewer).

apps/api/orchestrator.py calls three things here:

- current_probe_hint(db, round_) before the interviewer's turn (live mode only);
- schedule_after_turn(db, round_id) after each committed turn - extraction,
  belief update and the picker's decision, off the interviewer's critical path;
- catch_up(db, round_id) at submit, so every answer is processed before the
  report is read.

Everything is wrapped so a world-model failure is logged and never blocks an
interview or a submit. Diagnosis and the path map are recomputed from the
wm_* event rows on every read (build_report) - nothing derived is stored.
"""
from __future__ import annotations

import logging
import os
import threading
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from apps.api.db import SessionLocal
from apps.api.models import (
    RoundAttempt,
    TranscriptTurn,
    WMBeliefSnapshot,
    WMDecision,
    WMEvidence,
    WMProcessedTurn,
    WMRetry,
    WMRewrite,
)
from roundzero.worldmodel import belief as bl
from roundzero.worldmodel import config, picker, steering
from roundzero.worldmodel.diagnosis import answer_turns, diagnose, probed_dims_for, question_for
from roundzero.worldmodel.extractor import Extractor, RuleBasedExtractor, get_extractor
from roundzero.worldmodel.flip import FlipWriter, generate_rewrites, get_flip_writer
from roundzero.worldmodel.models import Decision, Evidence, FlipRewrite, RetryResult, WorldModelReport
from roundzero.worldmodel.retry import score_retry

logger = logging.getLogger("roundzero.worldmodel.service")

_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


class FlipUnavailableError(Exception):
    pass


def _lock_for(round_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks[round_id]


def _time_remaining_sec(round_: RoundAttempt) -> int:
    if round_.started_at is None:
        return round_.duration_minutes * 60
    started = round_.started_at if round_.started_at.tzinfo else round_.started_at.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    return max(0, round(round_.duration_minutes * 60 - elapsed))


def turn_dicts(db: DBSession, round_id: str) -> list[dict]:
    rows = (
        db.query(TranscriptTurn)
        .filter(TranscriptTurn.round_id == round_id)
        .order_by(TranscriptTurn.turn_index)
        .all()
    )
    return [
        {"turn_index": t.turn_index, "speaker": t.speaker, "text": t.text, "competency_tags": t.competency_tags or []}
        for t in rows
    ]


def load_evidence(db: DBSession, round_id: str) -> list[Evidence]:
    rows = (
        db.query(WMEvidence)
        .filter(WMEvidence.round_id == round_id)
        .order_by(WMEvidence.turn_index, WMEvidence.created_at)
        .all()
    )
    return [
        Evidence(
            turn_index=r.turn_index,
            dimension=r.dimension,
            competency=r.competency,
            criterion=r.criterion,
            polarity=r.polarity,
            span=r.span,
            strength=r.strength,
            extractor_version=r.extractor_version,
        )
        for r in rows
    ]


def process_round(db: DBSession, round_id: str, extractor: Extractor | None = None) -> int:
    """Extract evidence for every unprocessed candidate answer, snapshot the
    belief, and log the picker's decision. Idempotent. Returns how many answers
    were processed."""
    if not config.wm_enabled():
        return 0
    round_ = db.get(RoundAttempt, round_id)
    if round_ is None:
        return 0
    comps = config.round_competencies(round_.round_type)
    if not comps:
        return 0
    turns = turn_dicts(db, round_id)
    answers = answer_turns(turns)
    done = {r.turn_index for r in db.query(WMProcessedTurn).filter(WMProcessedTurn.round_id == round_id).all()}
    pending = [t for t in answers if t not in done]
    if not pending:
        return 0

    extractor = extractor or get_extractor()
    text_by_turn = {t["turn_index"]: t["text"] for t in turns}
    mode = config.adaptive_mode()
    for turn in pending:
        items = extractor.extract(
            round_type=round_.round_type,
            question=question_for(turns, turn),
            answer=text_by_turn[turn],
            turn_index=turn,
            probed_dims=probed_dims_for(turns, turn),
        )
        for ev in items:
            db.add(WMEvidence(round_id=round_id, **ev.model_dump()))
        db.add(WMProcessedTurn(round_id=round_id, turn_index=turn, extractor_version=extractor.version))
        db.flush()

        evidence = load_evidence(db, round_id)
        belief = bl.final_belief(round_.level, comps, [t for t in answers if t <= turn], evidence)
        db.add(WMBeliefSnapshot(round_id=round_id, turn_index=turn, probs=belief.probs))

        if mode != "off":
            recent = [
                d.chosen_competency
                for d in db.query(WMDecision)
                .filter(WMDecision.round_id == round_id)
                .order_by(WMDecision.after_turn_index)
                .all()
                if d.chosen_competency
            ]
            decision = picker.choose(
                belief,
                after_turn_index=turn,
                recent_choices=recent,
                time_remaining_sec=_time_remaining_sec(round_),
                mode=mode,
            )
            db.add(
                WMDecision(
                    round_id=round_id,
                    after_turn_index=turn,
                    mode=mode,
                    chosen_competency=decision.chosen.competency if decision.chosen else None,
                    payload=decision.model_dump(),
                )
            )
        db.commit()
    return len(pending)


def catch_up(db: DBSession, round_id: str, extractor: Extractor | None = None) -> int:
    """Synchronous, caller's session. Never raises."""
    try:
        with _lock_for(round_id):
            return process_round(db, round_id, extractor)
    except Exception:
        logger.exception("world-model catch-up failed for round_id=%s", round_id)
        db.rollback()
        return 0


def _process_in_own_session(round_id: str) -> None:
    with SessionLocal() as db:
        catch_up(db, round_id)


def schedule_after_turn(db: DBSession, round_id: str, extractor: Extractor | None = None) -> None:
    """Runs inline when the extractor is rule-based (instant) or
    ROUNDZERO_WM_SYNC=1; otherwise on a daemon thread with its own session so
    the extractor's LLM call never delays the interviewer's reply."""
    if not config.wm_enabled():
        return
    try:
        extractor = extractor or get_extractor()
        sync = config.sync_override()
        if sync is None:
            sync = isinstance(extractor, RuleBasedExtractor)
        if sync:
            catch_up(db, round_id, extractor)
        else:
            threading.Thread(target=_process_in_own_session, args=(round_id,), daemon=True).start()
    except Exception:
        logger.exception("could not schedule world-model processing for round_id=%s", round_id)


def current_probe_hint(db: DBSession, round_: RoundAttempt) -> str | None:
    """Live mode only: the latest decision's chosen probe, rendered as an
    internal note for the interviewer. None in shadow/off mode."""
    if not config.wm_enabled() or config.adaptive_mode() != "live":
        return None
    try:
        latest = (
            db.query(WMDecision)
            .filter(WMDecision.round_id == round_.id)
            .order_by(WMDecision.after_turn_index.desc())
            .first()
        )
        if latest is None or not latest.chosen_competency:
            return None
        return steering.render_probe_hint(Decision.model_validate(latest.payload).chosen)
    except Exception:
        logger.exception("could not build probe hint for round_id=%s", round_.id)
        return None


def flip_available() -> bool:
    return config.flip_enabled() and bool(os.environ.get("OPENAI_API_KEY"))


def build_report(db: DBSession, round_: RoundAttempt) -> WorldModelReport:
    turns = turn_dicts(db, round_.id)
    evidence = load_evidence(db, round_.id)
    processed = db.query(WMProcessedTurn).filter(WMProcessedTurn.round_id == round_.id).all()
    diagnoses = diagnose(round_type=round_.round_type, target_level=round_.level, turns=turns, evidence=evidence)
    rewrites = [
        FlipRewrite.model_validate({**r.payload, "id": r.id})
        for r in db.query(WMRewrite).filter(WMRewrite.round_id == round_.id).order_by(WMRewrite.created_at).all()
    ]
    retries = [
        RetryResult.model_validate({**r.payload, "id": r.id})
        for r in db.query(WMRetry).filter(WMRetry.round_id == round_.id).order_by(WMRetry.created_at).all()
    ]
    return WorldModelReport(
        round_id=round_.id,
        round_type=round_.round_type,
        target_level=round_.level,
        adaptive_mode=config.adaptive_mode(),
        extractor_version=processed[-1].extractor_version if processed else None,
        answers_processed=len(processed),
        answers_total=len(answer_turns(turns)),
        competencies=diagnoses,
        rewrites=rewrites,
        retries=retries,
        flip_available=flip_available(),
        decisions_logged=db.query(WMDecision).filter(WMDecision.round_id == round_.id).count(),
    )


def create_rewrites(
    db: DBSession,
    round_: RoundAttempt,
    writer: FlipWriter | None = None,
    scorer: Extractor | None = None,
) -> list[FlipRewrite]:
    if not config.flip_enabled():
        raise FlipUnavailableError("Flip rewrites are turned off (ROUNDZERO_WM_FLIP=0).")
    writer = writer or get_flip_writer()
    if writer is None:
        raise FlipUnavailableError("Flip rewrites need the evaluator model (OPENAI_API_KEY is not set).")
    scorer = scorer or get_extractor()
    catch_up(db, round_.id, scorer)

    turns = turn_dicts(db, round_.id)
    evidence = load_evidence(db, round_.id)
    diagnoses = diagnose(round_type=round_.round_type, target_level=round_.level, turns=turns, evidence=evidence)
    existing = {(r.competency, r.turn_index) for r in db.query(WMRewrite).filter(WMRewrite.round_id == round_.id)}
    todo = [d for d in diagnoses if d.causes and (d.competency, d.causes[0].turn_index) not in existing]
    new = generate_rewrites(
        round_type=round_.round_type,
        target_level=round_.level,
        turns=turns,
        evidence=evidence,
        diagnoses=todo,
        writer=writer,
        scorer=scorer,
    )
    for rw in new:
        db.add(WMRewrite(round_id=round_.id, competency=rw.competency, turn_index=rw.turn_index,
                         payload=rw.model_dump(exclude={"id"})))
    db.commit()
    return build_report(db, round_).rewrites


def create_retry(
    db: DBSession,
    round_: RoundAttempt,
    user_id: str,
    turn_index: int,
    text: str,
    scorer: Extractor | None = None,
) -> RetryResult:
    scorer = scorer or get_extractor()
    catch_up(db, round_.id, scorer)
    result = score_retry(
        round_type=round_.round_type,
        target_level=round_.level,
        turns=turn_dicts(db, round_.id),
        evidence=load_evidence(db, round_.id),
        turn_index=turn_index,
        retry_text=text,
        scorer=scorer,
    )
    row = WMRetry(round_id=round_.id, user_id=user_id, turn_index=turn_index, retry_text=text,
                  payload=result.model_dump(exclude={"id"}))
    db.add(row)
    db.commit()
    return result.model_copy(update={"id": row.id})


def competency_trend(db: DBSession, user_id: str, limit: int = 30) -> list[dict]:
    """Final believed level per competency for each evaluated round with
    world-model data, oldest first - the Progress page's across-sessions view."""
    rounds = (
        db.query(RoundAttempt)
        .filter(RoundAttempt.user_id == user_id, RoundAttempt.status == "EVALUATED")
        .order_by(RoundAttempt.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    for r in reversed(rounds):
        evidence = load_evidence(db, r.id)
        if not evidence:
            continue
        turns = turn_dicts(db, r.id)
        diagnoses = diagnose(round_type=r.round_type, target_level=r.level, turns=turns, evidence=evidence)
        out.append(
            {
                "round_id": r.id,
                "round_type": r.round_type,
                "created_at": r.created_at,
                "levels": [
                    {
                        "competency": d.competency,
                        "label": d.label,
                        "mean": d.final_mean,
                        "level": d.final_level,
                        "abstained": d.abstained,
                    }
                    for d in diagnoses
                ],
            }
        )
    return out
