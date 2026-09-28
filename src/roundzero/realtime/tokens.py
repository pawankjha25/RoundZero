"""
LiveKit room-join credential minting for voice-mode interview rounds.

Mirrors the rest of the codebase's provider conventions: is_configured()/the
env-var-presence check lives here (same shape as
apps/api/orchestrator.get_gateway()'s "if os.environ.get(KEY): return
RealImpl()" chain), and mint_livekit_token()/get_livekit_url() raise
RealtimeNotConfiguredError rather than ever fabricating a token or URL - the
same "never fabricate a result" convention as
roundzero.coding.execution.MockCodeExecutionProvider (which returns
passed=None rather than inventing a pass/fail). Callers (the voice/token
route) turn that exception into a clean 503 so the frontend can degrade
gracefully back to text, per specs/001-ml-system-design-vertical-slice/
milestone-4.md's runtime-flow step 7.

This module only mints tokens for the FastAPI-side "join this room" request.
The actual interview logic lives in src/roundzero/realtime/agent.py, a
separate long-running LiveKit Agents worker process - not this module, and
not the FastAPI process either.
"""
from __future__ import annotations

import os
from datetime import timedelta

from livekit.api import AccessToken, VideoGrants

_REQUIRED_ENV_VARS = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "DEEPGRAM_API_KEY")

# Short-lived on purpose - a candidate joins once per voice session; minting a
# fresh token per /voice/token request (rather than caching) means a leaked
# token is only ever valid for this long.
_TOKEN_TTL = timedelta(hours=1)


class RealtimeNotConfiguredError(Exception):
    """Raised when LiveKit/Deepgram env vars aren't set. Never caught to
    silently fall back to a fake token - callers should surface this as a
    503 and let the frontend degrade to text, not paper over it."""


def is_configured() -> bool:
    """True only when every LiveKit + Deepgram env var is present. All four
    are needed for a voice round to actually work end-to-end (LiveKit for the
    room/transport, Deepgram for the agent worker's STT+TTS) - partial config
    is treated the same as no config, since a half-configured voice mode
    would fail confusingly mid-round rather than degrading cleanly up front."""
    return all(os.environ.get(var) for var in _REQUIRED_ENV_VARS)


def get_livekit_url() -> str:
    url = os.environ.get("LIVEKIT_URL")
    if not url:
        raise RealtimeNotConfiguredError("LIVEKIT_URL is not set.")
    return url


def room_name_for_round(round_id: str) -> str:
    """One room per round, deterministically named - the agent worker
    (agent.py) recovers round_id from this same name when a job is
    dispatched, without needing a separate side channel."""
    return f"round-{round_id}"


def mint_livekit_token(*, room_name: str, identity: str, name: str | None = None) -> str:
    """A candidate-side join token: can publish (their mic) and subscribe
    (the agent's TTS audio), scoped to exactly one room. Raises
    RealtimeNotConfiguredError rather than returning anything when
    LIVEKIT_API_KEY/LIVEKIT_API_SECRET aren't set."""
    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")
    if not api_key or not api_secret:
        raise RealtimeNotConfiguredError("LIVEKIT_API_KEY / LIVEKIT_API_SECRET are not set.")

    grants = VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True)
    token = (
        AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(name or identity)
        .with_grants(grants)
        .with_ttl(_TOKEN_TTL)
    )
    return token.to_jwt()
