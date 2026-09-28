"""
Core interview contracts: TargetRole, conversation state, interviewer input/output.
See docs/PRD.md section 21 (Agent Contracts) and section 37 ticket 1.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from roundzero.domain.enums import CoverageStatus, InterviewerAction, Phase

# Must match the dimension keys in rubrics/ml_system_design/v1.yaml.
RUBRIC_DIMENSIONS = [
    "framing",
    "architecture",
    "modeling",
    "data_training",
    "serving_scalability",
    "reliability",
    "evaluation_monitoring",
    "cost_efficiency",
    "trade_offs",
    "communication",
]


def default_coverage() -> dict[str, CoverageStatus]:
    return {dim: CoverageStatus.NOT_COVERED for dim in RUBRIC_DIMENSIONS}


# Slug -> readable-word overrides for TargetRole.describe() below - same
# small exception-list pattern apps/api/orchestrator.py's own _title_word
# uses for loop-name generation (kept separate rather than shared, since
# src/roundzero must not import from apps/api - the dependency runs the
# other way, apps/api -> src/roundzero, per CLAUDE.md decision 1).
_LABEL_WORD_OVERRIDES = {"ml": "ML", "ai": "AI", "llm": "LLM", "genai": "GenAI", "xfn": "Cross-functional"}


def _format_slug(value: str) -> str:
    return " ".join(_LABEL_WORD_OVERRIDES.get(w, w.capitalize()) for w in value.split("_"))


class TargetRole(BaseModel):
    role_family: str
    level: str
    domain: str
    company_profile: str = "generic"

    def describe(self) -> str:
        """Human-readable one-line summary of this target, e.g. "Staff ML
        Infra Engineer role, ML Infra domain, targeting a Big Tech company."
        Added so every interviewer's prompt can actually state who it's
        interviewing and for what, instead of leaving level/domain to be
        inferred only implicitly from which scenario got picked
        (pick_scenario already filters by level+domain; company_profile was
        previously never surfaced to the model at all - specs/002
        personalization gap, fixed 2026-09-03). "generic" company_profile
        (the default/no-specific-company choice) is omitted rather than
        rendered as "targeting a Generic company", which would read oddly -
        every real interviewer prompt already falls back to a sensible
        default persona in that case (see e.g.
        prompts/interviewers/ml_system_design/v1.md's "top-tier technology
        company" framing)."""
        parts = [
            f"{_format_slug(self.level)} {_format_slug(self.role_family)} role",
            f"{_format_slug(self.domain)} domain",
        ]
        if self.company_profile and self.company_profile != "generic":
            parts.append(f"targeting a {_format_slug(self.company_profile)} company")
        return ", ".join(parts)


class ConversationTurn(BaseModel):
    speaker: str  # "interviewer" | "candidate"
    text: str
    phase: Phase
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationState(BaseModel):
    """Mutable state threaded through the turn loop for one round."""

    phase: Phase = Phase.INTRO
    time_remaining_sec: int
    coverage: dict[str, CoverageStatus] = Field(default_factory=default_coverage)
    turns: list[ConversationTurn] = Field(default_factory=list)


class InterviewerInput(BaseModel):
    """PRD section 21.1 - what the orchestrator hands the interviewer each turn."""

    round_type: str = "ml_system_design"
    target_role: TargetRole
    scenario: str
    rubric_summary: list[str]  # dimension names only - never anchors/weights, PRD sec 8
    time_remaining_sec: int
    conversation_state: ConversationState
    candidate_artifacts: dict = Field(default_factory=dict)


class InterviewerOutput(BaseModel):
    """PRD section 21.2 - what the interviewer returns each turn."""

    utterance: str
    action: InterviewerAction
    competency_tags: list[str] = Field(default_factory=list)
    phase: Phase
    coverage: dict[str, CoverageStatus]
    tool_request: Optional[dict] = None
