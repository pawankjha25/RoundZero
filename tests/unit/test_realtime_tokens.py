"""
src/roundzero/realtime/tokens.py - no live LiveKit connection, same "no
network" convention as every other test file in this directory. Exercises
is_configured()'s all-four-vars-required behavior and mint_livekit_token()'s
"never fabricate, raise instead" contract, plus a happy-path token decoded
locally to assert its grants actually scope the candidate to one room.
"""
from __future__ import annotations

import jwt
import pytest

from roundzero.realtime.tokens import (
    RealtimeNotConfiguredError,
    get_livekit_url,
    is_configured,
    mint_livekit_token,
    room_name_for_round,
)

_ALL_VARS = {
    "LIVEKIT_URL": "wss://fake.livekit.cloud",
    "LIVEKIT_API_KEY": "fakekey",
    "LIVEKIT_API_SECRET": "fakesecretfakesecretfakesecret12",
    "DEEPGRAM_API_KEY": "fakedg",
}


def _clear_env(monkeypatch):
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)


def test_is_configured_false_when_nothing_set(monkeypatch):
    _clear_env(monkeypatch)
    assert is_configured() is False


def test_is_configured_false_when_only_partially_set(monkeypatch):
    """A half-configured voice mode (e.g. LiveKit keys but no Deepgram key)
    should fail the same clean, up-front way as no config at all - not fail
    confusingly mid-round."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("LIVEKIT_URL", _ALL_VARS["LIVEKIT_URL"])
    monkeypatch.setenv("LIVEKIT_API_KEY", _ALL_VARS["LIVEKIT_API_KEY"])
    monkeypatch.setenv("LIVEKIT_API_SECRET", _ALL_VARS["LIVEKIT_API_SECRET"])
    assert is_configured() is False


def test_is_configured_true_when_all_four_set(monkeypatch):
    _clear_env(monkeypatch)
    for key, value in _ALL_VARS.items():
        monkeypatch.setenv(key, value)
    assert is_configured() is True


def test_mint_livekit_token_raises_when_unconfigured_never_fabricates(monkeypatch):
    _clear_env(monkeypatch)
    with pytest.raises(RealtimeNotConfiguredError):
        mint_livekit_token(room_name="round-abc", identity="user-1")


def test_get_livekit_url_raises_when_unconfigured(monkeypatch):
    _clear_env(monkeypatch)
    with pytest.raises(RealtimeNotConfiguredError):
        get_livekit_url()


def test_room_name_for_round_is_deterministic():
    assert room_name_for_round("abc-123") == "round-abc-123"


def test_mint_livekit_token_happy_path_scopes_to_one_room(monkeypatch):
    _clear_env(monkeypatch)
    for key, value in _ALL_VARS.items():
        monkeypatch.setenv(key, value)

    token = mint_livekit_token(room_name="round-abc-123", identity="user-1")
    claims = jwt.decode(
        token,
        _ALL_VARS["LIVEKIT_API_SECRET"],
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    assert claims["sub"] == "user-1"
    assert claims["iss"] == _ALL_VARS["LIVEKIT_API_KEY"]
    grants = claims["video"]
    assert grants["room"] == "round-abc-123"
    assert grants["roomJoin"] is True
    assert grants["canPublish"] is True
    assert grants["canSubscribe"] is True
