"""
Pure-Python text helpers for the voice pipeline (roundzero.realtime.agent) -
split out into their own module specifically so they can be unit tested
without importing agent.py itself. agent.py has a module-level load_dotenv()
call (it needs LIVEKIT_*/DEEPGRAM_API_KEY from the repo's .env at import
time) that leaks real secrets - including OPENAI_API_KEY - into the whole
pytest process once imported; see test_admin_and_report.py's module
docstring for the exact same hazard already documented for apps.api.main.
No test file should ever import roundzero.realtime.agent directly - import
from here instead for anything that doesn't need a live LiveKit session.
"""
from __future__ import annotations

import re

# Voice latency fix (2026-09-03): the candidate previously heard nothing at
# all while orchestrator.post_message()'s blocking LLM call was in flight
# (1-5s+, see agent.py's llm_node()) - a short filler spoken immediately
# masks that wait the way a real interviewer's own "mm, let's see" would.
# Kept short and generic on purpose: it's spoken before we know anything
# about what the reply will actually be, so it can't reference content.
THINKING_FILLERS = [
    "Mm, let's see.",
    "Okay, one moment.",
    "Right, let me think.",
    "Hmm, okay.",
    "Got it, let's see.",
]

# Splits the interviewer's reply into sentence-sized chunks so TTS can start
# synthesizing/speaking the first sentence without waiting for the whole
# reply to be ready - it's already short (voice_mode's prompt instructs
# 1-3 sentences), so this mostly just removes the "wait for everything, then
# speak" lag on replies that do run to 2-3 sentences. A lookbehind on
# ./!/? keeps the punctuation attached to the sentence it ends.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_into_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text.strip()) if p.strip()]
    return parts or [text]
