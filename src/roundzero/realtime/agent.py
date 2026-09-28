"""
LiveKit Agents worker - the actual voice-mode interview process. Run as its
own long-running process (`python -m roundzero.realtime.agent dev`, see the
repo README for the exact command), separate from uvicorn and next dev -
FastAPI only mints room-join tokens (tokens.py); this file is what joins the
room and runs the interview.

Bridges LiveKit's STT/turn-detection/TTS pipeline into the *exact same*
apps.api.orchestrator.post_message() call the text-chat path already uses -
see milestone-4.md's "why this milestone is mostly a transport swap" section:
this file deliberately does not reimplement or touch the interviewer/
evaluation logic, it only supplies it with text and speaks its replies back.
Both transports persist identical TranscriptTurn rows, so the report/
evaluation pipeline never needs to know which one produced a given turn.

Runs on the same machine/repo as the FastAPI app and talks to SQLite
directly via apps.api.db.SessionLocal - it's trusted server-side code, not a
client, so there's no separate service-to-service auth to invent here.

Does not enable LiveKit room recording/egress anywhere - no raw audio is
retained by default, per milestone-4.md's Decision 2 (delete-by-default,
opt-in to keep).
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
from pathlib import Path
from typing import AsyncIterable

from dotenv import load_dotenv

# Load the same .env the FastAPI app reads - this worker imports apps.api
# directly below and needs DATABASE_URL/DEEPGRAM_API_KEY/etc. from it too.
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli  # noqa: E402
from livekit.agents import llm as agents_llm  # noqa: E402
from livekit.agents.llm import ChatContext  # noqa: E402
from livekit.plugins import deepgram  # noqa: E402

from apps.api import orchestrator  # noqa: E402
from apps.api.db import SessionLocal  # noqa: E402
from apps.api.models import RoundAttempt, TranscriptTurn  # noqa: E402
from roundzero.realtime.voice_text import THINKING_FILLERS, split_into_sentences  # noqa: E402

logger = logging.getLogger("roundzero.realtime.agent")

_ROOM_NAME_RE = re.compile(r"^round-(?P<round_id>.+)$")


def round_id_from_room_name(room_name: str) -> str | None:
    """Rooms are named round-{round_id} (see tokens.room_name_for_round) -
    this is the only side channel the worker needs to find its round."""
    match = _ROOM_NAME_RE.match(room_name)
    return match.group("round_id") if match else None


class _UnusedLLM(agents_llm.LLM):
    """AgentSession refuses to generate any reply at all when session.llm is
    None (see livekit-agents' agent_activity.py:
    "elif self.llm is None: return  # skip response if no llm is set") - this
    check runs *before* Agent.llm_node() is ever reached, even though
    RoundZeroVoiceAgent overrides llm_node() and never touches session.llm
    itself. This stub exists purely to satisfy that not-None check; its
    chat() should never actually be invoked, so it raises loudly if it ever
    is - that would mean something in livekit-agents bypassed llm_node()."""

    def chat(self, **kwargs):  # noqa: ANN003
        raise NotImplementedError(
            "RoundZeroVoiceAgent.llm_node() should always intercept generation "
            "before LLM.chat() is called."
        )


class RoundZeroVoiceAgent(Agent):
    """An Agent whose "LLM step" (llm_node) is actually a call into
    apps.api.orchestrator.post_message() - the identical function
    apps/api/routes/rounds.py's POST /message endpoint calls for the text
    path. STT, turn-detection, and TTS are all handled by the surrounding
    AgentSession/framework; this class only supplies candidate text in and
    gets the interviewer's reply text out, per llm_node()'s documented
    contract (it may be an async generator yielding str chunks)."""

    def __init__(self, round_id: str):
        super().__init__(
            instructions=(
                "You bridge a LiveKit voice call into Round Zero's existing "
                "ml_system_design interviewer - see class docstring. This "
                "instructions string is unused: llm_node() is overridden and "
                "never calls a real LLM."
            )
        )
        self._round_id = round_id

    async def llm_node(self, chat_ctx: ChatContext, tools, model_settings) -> AsyncIterable[str]:
        candidate_text = None
        for item in reversed(chat_ctx.items):
            if getattr(item, "role", None) == "user":
                candidate_text = item.text_content
                break
        if not candidate_text:
            logger.warning("llm_node called with no finalized user text in chat_ctx - nothing to reply to.")
            return

        logger.info("candidate (voice, round=%s): %r", self._round_id, candidate_text)

        # Speak a short filler immediately, before the blocking call below even
        # starts - see voice_text.THINKING_FILLERS' docstring. TTS begins synthesizing
        # this chunk right away while _advance_turn runs on its own thread, so
        # the candidate hears something near-instantly instead of dead air.
        yield random.choice(THINKING_FILLERS)

        try:
            # orchestrator.post_message() is synchronous SQLAlchemy + a
            # blocking LLM HTTP call - running it directly here would stall
            # this agent's asyncio event loop (and everyone else's turn
            # detection/audio) for the whole call. asyncio.to_thread() runs
            # it on a worker thread instead, same contract, same TranscriptTurn
            # rows, just off the event loop.
            reply_text = await asyncio.to_thread(self._advance_turn, candidate_text)
        except Exception:
            # Never let an LLM/DB hiccup produce dead silence - the candidate
            # is on a live call and needs *some* spoken response. Logged in
            # full here so the worker's terminal shows the real traceback.
            logger.exception("Voice turn failed for round_id=%s", self._round_id)
            yield "Sorry, I hit an error on my end - could you repeat that, or we can continue by text?"
            return

        logger.info("interviewer (voice, round=%s): %r", self._round_id, reply_text)
        # Yield sentence-by-sentence rather than the whole reply at once - see
        # voice_text.split_into_sentences' docstring. Each yielded chunk lets TTS start
        # on it without waiting for later sentences to be ready.
        for sentence in split_into_sentences(reply_text):
            yield sentence

    def _advance_turn(self, candidate_text: str) -> str:
        """Runs on a worker thread (see llm_node) - opens its own short-lived
        DB session, same lifecycle as a single FastAPI request handler."""
        db = SessionLocal()
        try:
            round_ = db.get(RoundAttempt, self._round_id)
            if round_ is None:
                logger.error("Voice session for unknown round_id=%r - ending.", self._round_id)
                return "Sorry, I've lost track of this round. Please continue by text."
            if round_.status not in ("ACTIVE", "WRAP_UP"):
                return "This round has already ended - check the report page for your results."
            turn = orchestrator.post_message(db, round_, candidate_text)
            return turn.text
        finally:
            db.close()


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    round_id = round_id_from_room_name(ctx.room.name)
    if round_id is None:
        logger.error("Room name %r doesn't match round-<id> - refusing to start a session.", ctx.room.name)
        return

    session = AgentSession(
        stt=deepgram.STT(
            # Deepgram's default endpointing_ms=25 is tuned for short,
            # clipped commands - it was cutting normal sentences into
            # fragments on a brief mid-sentence pause (e.g. "Is this a sixty
            # minute" / "or forty five minute interview?" as two separate
            # turns). 500ms gives a natural speaking pause room to breathe
            # before committing a turn. utterance_end_ms is a second,
            # coarser signal for the same problem - Deepgram requires it be
            # >= 1000 when set.
            endpointing_ms=500,
            utterance_end_ms=1000,
        ),
        tts=deepgram.TTS(),
        # Deepgram's own endpointing drives turn detection - no separate VAD
        # plugin/dependency needed for this pass. `llm` is the _UnusedLLM
        # stub, not a real model - see its docstring for why it's required
        # anyway (AgentSession silently drops every turn without *some*
        # non-None llm configured, regardless of the llm_node() override).
        llm=_UnusedLLM(),
        turn_detection="stt",
    )
    await session.start(agent=RoundZeroVoiceAgent(round_id=round_id), room=ctx.room)
    await _speak_latest_turn(session, round_id)


async def _speak_latest_turn(session: AgentSession, round_id: str) -> None:
    """Candidate feedback (2026-09-03): "AI was also not saying problem" -
    entrypoint() previously only ever *reacted* to candidate speech via
    llm_node(); nothing ever spoke first, so a candidate joining a fresh
    voice round heard silence even though the round's opening question
    already exists as a TranscriptTurn (written by orchestrator.create_round()
    the same way it is for the text path).

    Deliberately uses session.say() - pure TTS on already-decided text - and
    not session.generate_reply(), which would delegate to the LLM and risk
    generating a *second*, possibly-divergent opening turn. This speaks the
    exact turn the candidate would otherwise have had to read, sourced from
    the same TranscriptTurn row the text/report path already relies on."""
    db = SessionLocal()
    try:
        latest = (
            db.query(TranscriptTurn)
            .filter(TranscriptTurn.round_id == round_id, TranscriptTurn.speaker == "interviewer")
            .order_by(TranscriptTurn.turn_index.desc())
            .first()
        )
    finally:
        db.close()

    if latest is None:
        logger.warning("No interviewer turn found for round_id=%s - nothing to speak first.", round_id)
        return

    logger.info("speaking opening turn (voice, round=%s): %r", round_id, latest.text)
    try:
        await session.say(latest.text, allow_interruptions=False)
    except Exception:
        # Never let a TTS hiccup abort the whole session - the candidate can
        # still speak first and the reactive llm_node() path still works.
        logger.exception("Failed to speak opening turn for round_id=%s", round_id)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
