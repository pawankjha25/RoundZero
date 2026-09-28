"""
Deterministic mock gateway - lets you run the CLI harness end-to-end (phase loop,
coverage shape, JSON parsing) without a real API key. It cycles through scripted,
generic responses; it does NOT exercise real adaptive-probing quality - that needs
AnthropicGateway and an actual conversation. Swap back once you have a key.
"""
from __future__ import annotations

import json

from roundzero.domain.enums import CoverageStatus, InterviewerAction, Phase
from roundzero.domain.interview import RUBRIC_DIMENSIONS, default_coverage
from roundzero.llm.gateway import LLMGateway

_SCRIPT: list[tuple[Phase, InterviewerAction, str]] = [
    (Phase.INTRO, InterviewerAction.ASK,
     "Let's get started - can you restate the problem in your own words and ask me any clarifying questions?"),
    (Phase.REQUIREMENTS, InterviewerAction.PROBE,
     "What scale are we talking about - how many models, how many requests per second at peak?"),
    (Phase.HIGH_LEVEL_DESIGN, InterviewerAction.ASK,
     "Walk me through the high-level architecture you're proposing."),
    (Phase.HIGH_LEVEL_DESIGN, InterviewerAction.PROBE,
     "How would you prevent one tenant from monopolizing GPU capacity?"),
    (Phase.ML_MODEL_ARCHITECTURE, InterviewerAction.ASK,
     "How are models packaged and versioned for serving?"),
    (Phase.DATA_TRAINING, InterviewerAction.ASK,
     "How do teams get their models onto this platform in the first place?"),
    (Phase.SERVING_SCALE, InterviewerAction.PROBE,
     "Traffic increases 10x during peak hours. Walk me through your autoscaling strategy."),
    (Phase.RELIABILITY, InterviewerAction.PROBE,
     "Your p99 latency suddenly jumps while GPU utilization remains at 40%. How would you investigate?"),
    (Phase.EVALUATION_MONITORING, InterviewerAction.ASK,
     "How would you know if a newly deployed model is degrading in production before customers notice?"),
    (Phase.TRADEOFF_DEEP_DIVE, InterviewerAction.ASK,
     "What's the biggest trade-off in your design, and what would change your mind about it?"),
    (Phase.WRAP_UP, InterviewerAction.WRAP,
     "That's a good stopping point - thanks for walking me through your design."),
]


class MockLLMGateway(LLMGateway):
    """Scripted, stateful, deterministic - no network call, no API key needed.

    start_turn: lets a caller resynchronize the script position with however many
    interviewer turns already happened (apps/api/orchestrator.py instantiates a
    fresh gateway per request rather than keeping one alive across requests, since
    a long-lived FastAPI process would otherwise share one _turn counter across
    every candidate's round)."""

    def __init__(self, start_turn: int = 0):
        self._turn = start_turn

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        index = min(self._turn, len(_SCRIPT) - 1)
        phase, action, utterance = _SCRIPT[index]
        self._turn += 1

        coverage = {k: v.value for k, v in default_coverage().items()}
        covered_so_far = RUBRIC_DIMENSIONS[: min(index, len(RUBRIC_DIMENSIONS))]
        for dim in covered_so_far:
            coverage[dim] = CoverageStatus.WEAK.value

        return json.dumps(
            {
                "utterance": utterance,
                "action": action.value,
                "competency_tags": covered_so_far[-1:],
                "phase": phase.value,
                "coverage": coverage,
            }
        )
