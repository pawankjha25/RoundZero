"""
src/roundzero/realtime/voice_text.py - the pure-Python text helpers behind
the voice latency fix (2026-09-03): a spoken filler while the blocking LLM
call is in flight, and sentence-chunked TTS yielding instead of waiting for
the whole reply. No live LiveKit/Deepgram connection here, same "no network"
convention as every other test file in this directory.

Deliberately imports from roundzero.realtime.voice_text, never
roundzero.realtime.agent - agent.py has a module-level load_dotenv() call
(needs LIVEKIT_*/DEEPGRAM_API_KEY at import time) that would leak the repo's
real OPENAI_API_KEY/etc. into this pytest process and break every other test
file's "no OPENAI_API_KEY -> RuleBasedEvaluator" assumption, exactly the
hazard test_admin_and_report.py's module docstring documents for
apps.api.main. voice_text.py exists specifically so this logic is testable
without that risk.

The voice pipeline's actual audio behavior (does the filler genuinely mask
latency, does TTS actually start sooner) isn't unit-testable and needs a
real voice call to judge.
"""
from __future__ import annotations

from roundzero.realtime.voice_text import THINKING_FILLERS, split_into_sentences


def test_split_into_sentences_splits_on_terminal_punctuation_and_keeps_it_attached():
    assert split_into_sentences("Sure, tell me more. What was the bottleneck?") == [
        "Sure, tell me more.",
        "What was the bottleneck?",
    ]


def test_split_into_sentences_handles_exclamation_and_single_sentence_replies():
    assert split_into_sentences("Interesting! How did you measure that?") == [
        "Interesting!",
        "How did you measure that?",
    ]
    assert split_into_sentences("Okay, go ahead.") == ["Okay, go ahead."]


def test_split_into_sentences_never_returns_an_empty_list():
    # No terminal punctuation, or empty input - always at least one chunk to
    # yield, since llm_node() must never yield zero chunks for a real reply.
    assert split_into_sentences("no punctuation here") == ["no punctuation here"]
    assert split_into_sentences("") == [""]


def test_thinking_fillers_are_all_short_nonempty_strings():
    # Kept short and content-free on purpose - spoken before the real reply
    # is known, so none of these should look like they're answering anything.
    assert len(THINKING_FILLERS) >= 3
    assert all(isinstance(f, str) and 0 < len(f) <= 40 for f in THINKING_FILLERS)
