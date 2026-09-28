"""
Request/response shapes for the rounds API - apps/api/routes/rounds.py,
apps/api/routes/config.py. Kept separate from apps/api/models.py (DB tables) and
roundzero.domain/roundzero.evaluation (core contracts) - this layer is the BFF's
own view, allowed to reshape either for the frontend without touching either.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from roundzero.evaluation.models import RoundEvaluation


class OptionOut(BaseModel):
    value: str
    label: str


class RoundTypeOptionOut(BaseModel):
    value: str
    label: str
    enabled: bool


class CompanyOptionOut(BaseModel):
    """Same as OptionOut plus `tier` - a cosmetic-only interview-complexity
    grouping an admin can tag a company with (frontier-ai-labs / big-tech /
    growth-stage / early-stage / enterprise-other, see
    apps/web/lib/companyTiers.ts). None until an admin sets one. Doesn't
    change interviewer behavior - see CompanyProfileOption's docstring."""

    value: str
    label: str
    tier: str | None = None


class OptionsOut(BaseModel):
    """value = what pick_scenario() actually matches against (e.g. Phase/level
    slugs in scenarios.yaml), label = what the dropdown shows. Kept as
    value/label pairs, not bare strings, so the UI can read nicely without the
    backend having to match on display text."""

    role_families: list[OptionOut]
    levels: list[OptionOut]
    domains: list[OptionOut]
    companies: list[CompanyOptionOut]
    duration_minutes: list[int]
    round_types: list[RoundTypeOptionOut]


class StartRoundRequest(BaseModel):
    role_family: str
    level: str
    domain: str
    company_profile: str = "generic"
    duration_minutes: int = 45
    # "text" (default) | "voice" | "both" - see RoundAttempt.modality's docstring
    # in apps/api/models.py. Opt-in, per the milestone-4 spec's recommendation.
    mode: Literal["text", "voice", "both"] = "text"
    # Defaults to ml_system_design (the original single-round-type behavior,
    # before Coding got a real interviewer too) so existing callers that never
    # send this field are unaffected. Validated against
    # orchestrator.REAL_ROUND_TYPES at call time, not restricted to a Literal
    # here - the set of real interviewers can grow without a schema change,
    # same reasoning as start_planned_round's round_type (any PlannedRound
    # value is accepted, only starting it is gated).
    round_type: str = "ml_system_design"


class ProfileOut(BaseModel):
    """GET /v1/profile always returns this shape, all fields None before the
    candidate has ever saved anything - the frontend never has to special-case
    "no profile yet" as an error (mirrors WorkspaceStateOut's same pattern)."""

    current_role: str | None = None
    target_role: str | None = None
    years_experience: int | None = None
    experience_summary: str | None = None
    objective: str | None = None
    linkedin_url: str | None = None
    updated_at: datetime | None = None


class ProfileUpdateRequest(BaseModel):
    current_role: str | None = None
    target_role: str | None = None
    years_experience: int | None = None
    experience_summary: str | None = None
    objective: str | None = None
    linkedin_url: str | None = None


class TurnOut(BaseModel):
    speaker: str
    text: str
    phase: str
    turn_index: int
    created_at: datetime


class TimelineEventOut(BaseModel):
    """One row of GET /v1/rounds/{round_id}/timeline (Interview Replay,
    user-requested from the backlog's P0.9 note "OK to start with transcript
    + code/canvas timeline before full synced audio replay"). Merges
    TranscriptTurn rows and WorkspaceEvent rows (both already carry
    created_at - the "no per-timestamp replay data exists yet" blocker
    EvidenceDrawer.tsx's comment describes was about the API never exposing
    it, not the data not existing) into one chronological list -
    orchestrator.get_round_timeline builds `text` as a short human-readable
    summary for workspace events (they don't store full code/canvas
    snapshots, only kind + light metadata - see WorkspaceEvent's docstring),
    and the raw turn text for transcript turns."""

    kind: str  # "turn:interviewer" | "turn:candidate" | "code_change" | "run_attempt" | "test_result" | "canvas_change"
    text: str
    phase: str | None = None
    created_at: datetime


class RoundOut(BaseModel):
    id: str
    loop_attempt_id: str
    round_type: str
    modality: str
    role_family: str
    level: str
    domain: str
    company_profile: str
    duration_minutes: int
    status: str
    phase: str
    coverage: dict[str, str]
    time_remaining_sec: int
    created_at: datetime
    submitted_at: datetime | None = None
    scenario_prompt: str
    # Structured scenario data (title/constraints/entry_point/starter code/test
    # cases) for round types whose workspace needs more than the plain prompt
    # string - see RoundAttempt.scenario_meta's docstring in apps/api/models.py.
    # {} for ml_system_design (nothing to show beyond the interviewer's own
    # spoken introduction), populated for coding.
    scenario_meta: dict = {}


class RoundDetailOut(BaseModel):
    round: RoundOut
    transcript: list[TurnOut]


class VoiceTokenOut(BaseModel):
    """LiveKit room join credentials for a voice/both-modality round. Minted
    fresh per request (src/roundzero/realtime/tokens.py) - never cached, never
    fabricated when LiveKit/Deepgram aren't configured (see is_configured())."""

    url: str
    token: str
    room: str


class MessageRequest(BaseModel):
    text: str


class DrillRequest(BaseModel):
    """POST /v1/rounds/{round_id}/drill body ("Practice this weakness") -
    priority identifies which of that round's RoundEvaluation.improvement_plan
    items to drill (1 = highest priority, per ImprovementItem's docstring)."""

    priority: int


class HistoryItemOut(BaseModel):
    id: str
    loop_attempt_id: str
    round_type: str
    role_family: str
    level: str
    domain: str
    company_profile: str
    duration_minutes: int
    status: str
    readiness_pct: int | None = None
    hire_signal: str | None = None
    created_at: datetime
    submitted_at: datetime | None = None


class PlannedRoundIn(BaseModel):
    """One round to include when creating a loop (POST /v1/loops). Every
    round type is selectable (round_type isn't restricted here) - the ones
    without a real interviewer just come back with startable=False and can't
    actually be started yet (see PlannedRoundOut/orchestrator.REAL_ROUND_TYPES).
    role_family/level/domain/company_profile/mode apply to every round in the
    loop (one shared target-role config per loop, not one per round) -
    duration_minutes is still per round since round types naturally run
    different lengths."""

    round_type: str
    duration_minutes: int


class LoopCreateRequest(BaseModel):
    name: str
    role_family: str
    level: str
    domain: str
    company_profile: str = "generic"
    mode: Literal["text", "voice", "both"] = "text"
    rounds: list[PlannedRoundIn]


class LoopNameSuggestionOut(BaseModel):
    """GET /v1/loops/suggested-name response - a pre-filled starting point
    for the loop builder's free-text name field (orchestrator.suggest_loop_name),
    never auto-applied without the person able to see and edit it first."""

    name: str


class PlannedRoundOut(BaseModel):
    id: str
    round_type: str
    role_family: str
    level: str
    domain: str
    company_profile: str
    duration_minutes: int
    modality: str
    sort_order: int
    # True only if round_type has a real interviewer AND this round hasn't
    # been started yet (orchestrator.REAL_ROUND_TYPES) - never true once
    # `started` is set, since a round is only ever started once.
    startable: bool
    started: HistoryItemOut | None = None


class LoopOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    rounds: list[PlannedRoundOut]


class CommitteeReportOut(BaseModel):
    """GET/POST /v1/loops/{id}/committee response - specs/002-full-loop-platform
    P0.6. See apps/api/orchestrator.py::get_committee_report/generate_committee_report
    and src/roundzero/debrief/committee.py::CommitteeReport for how the fields
    below are produced (overall_readiness_pct/overall_hire_signal/confidence are
    deterministic; the rest is the committee synthesis prose)."""

    overall_readiness_pct: int
    overall_hire_signal: str
    confidence: str
    headline: str
    strengths: list[str]
    concerns: list[str]
    level_signal: str
    key_evidence: list[str]
    rounds_included: list[str]
    generated_at: datetime


class DimensionScoreDelta(BaseModel):
    """One rubric dimension's score across two of the candidate's own past
    rounds. `delta` is newer minus older - positive means improvement."""

    dimension: str
    label: str
    score_older: int
    score_newer: int
    delta: int


class RoundComparisonOut(BaseModel):
    """GET /v1/rounds/compare's response (tasks.md P1 item 16 - "a lightweight
    version of Longitudinal Progress... two-attempt comparison, not full trend
    tracking yet"). Always ordered round_older -> round_newer by created_at
    regardless of which order the two round ids were requested in, so every
    delta field consistently reads as "improvement over time." Pure
    arithmetic over two already-persisted EvaluationRecord rows - no new LLM
    call, so this works even while the interviewer/evaluator providers are
    down (see apps.api.orchestrator.compare_rounds)."""

    round_older: HistoryItemOut
    round_newer: HistoryItemOut
    evaluation_older: RoundEvaluation
    evaluation_newer: RoundEvaluation
    readiness_delta: int
    hire_signal_older: str
    hire_signal_newer: str
    dimension_deltas: list[DimensionScoreDelta]


class WorkspaceStateOut(BaseModel):
    """GET /workspace response - defaults (None/"python") when no row exists
    yet, so the frontend can always render without a null check on first load."""

    round_id: str
    code_language: str | None = None
    code_text: str | None = None
    canvas_scene: list[dict] | None = None
    canvas_summary: str | None = None
    updated_at: datetime | None = None


class CodeSaveRequest(BaseModel):
    code_language: str
    code_text: str


class CanvasSaveRequest(BaseModel):
    """canvas_scene is Excalidraw's `elements` array; canvas_summary is computed
    client-side by lib/workspace/summarizeScene.ts from that same array, so the
    backend never has to parse Excalidraw's element schema itself."""

    canvas_scene: list[dict]
    canvas_summary: str


class TestCaseIn(BaseModel):
    name: str
    input: str | None = None
    expected_output: str | None = None


class RunCodeRequest(BaseModel):
    language: str
    code: str
    test_cases: list[TestCaseIn] = []
    entry_point: str | None = None  # function name to call - required for real Python execution


# Re-exported so routes can type their response_model without importing across
# roundzero.evaluation directly in every route module.
RoundEvaluationOut = RoundEvaluation

# Re-exported the same way - the actual model lives in roundzero.coding.execution
# so CodeExecutionProvider implementations don't have to import the BFF's
# schemas layer, mirroring the RoundEvaluationOut re-export above.
from roundzero.coding.execution import CodeExecutionResult as RunCodeResult  # noqa: E402


# --- Real Interview Experience + Outcome (specs/002-full-loop-platform P0.11/P0.12) ---


class RealInterviewRoundIn(BaseModel):
    round_type_label: str
    question_family: str
    follow_ups: str = ""
    difficulty: str = ""


class StructureRequestIn(BaseModel):
    """POST /v1/real-interviews/structure - preview-only, nothing persisted.
    hints is a free-text summary (role/level/domain/company) the frontend
    already has from the form's other fields, passed through so the model has
    some context without a second round-trip."""

    raw_text: str
    hints: str = ""


class StructuredExperienceOut(BaseModel):
    rounds: list[RealInterviewRoundIn]
    self_assessment: str


class RealInterviewExperienceIn(BaseModel):
    company: str
    role_family: str
    level: str
    domain: str | None = None
    interview_date: datetime
    linked_loop_attempt_id: str | None = None
    rounds: list[RealInterviewRoundIn] = []
    notes: str | None = None
    self_assessment: str | None = None
    visibility: Literal["private", "anonymous", "community"] = "private"


class PredictionSnapshotOut(BaseModel):
    """Live-computed, never stored - see orchestrator.real_interview_prediction.
    source is "committee" when the linked loop reached a Virtual Hiring
    Committee verdict, or "round" when it falls back to that loop's best
    evaluated round (the loop never reached committee eligibility)."""

    source: Literal["committee", "round"]
    readiness_pct: int
    hire_signal: str


class RealInterviewOutcomeIn(BaseModel):
    status: Literal["rejected", "advanced", "offer", "withdrew", "no_response"]
    stage: str | None = None
    target_level: str | None = None
    offered_level: str | None = None
    notes: str | None = None


class RealInterviewOutcomeOut(RealInterviewOutcomeIn):
    updated_at: datetime


class RealInterviewExperienceOut(BaseModel):
    id: str
    company: str
    role_family: str
    level: str
    domain: str | None
    interview_date: datetime
    linked_loop_attempt_id: str | None
    rounds: list[RealInterviewRoundIn]
    notes: str | None
    self_assessment: str | None
    visibility: Literal["private", "anonymous", "community"]
    created_at: datetime
    updated_at: datetime
    outcome: RealInterviewOutcomeOut | None = None
    prediction: PredictionSnapshotOut | None = None


# --- Prep Plans (user-pitched feature: candidate-curated practice questions,
# not from the P0 backlog - see apps/api/models.py's PrepPlan/PrepPlanArea/
# PrepPlanQuestion docstrings and orchestrator.py's "Prep Plans" section) ---


class PrepPlanIn(BaseModel):
    name: str
    role_family: str
    level: str
    domain: str
    company_profile: str = "generic"
    duration_minutes: int = 45
    mode: Literal["text", "voice", "both"] = "text"


class PrepPlanAreaIn(BaseModel):
    round_type: str
    label: str


class QuestionProgressOut(BaseModel):
    """Live-computed, never stored - see orchestrator._question_progress.
    attempts=0 means never tried. latest_* fields reflect the most recently
    *evaluated* attempt of this question, or None if it's never been
    attempted or nothing has finished evaluating yet."""

    attempts: int
    latest_status: str | None = None
    latest_readiness_pct: int | None = None
    latest_hire_signal: str | None = None


class AddBankQuestionIn(BaseModel):
    scenario_id: str


class AddCustomQuestionIn(BaseModel):
    prompt: str
    notes: str | None = None


class PrepPlanQuestionOut(BaseModel):
    id: str
    area_id: str
    prompt: str
    notes: str | None
    source: Literal["bank", "custom", "ai"]
    scenario_id: str | None
    progress: QuestionProgressOut


class BankScenarioOut(BaseModel):
    """One entry from GET /v1/prep-plans/areas/{id}/bank-scenarios - a real,
    runnable scenario from that round type's YAML bank, filtered to the
    plan's level/domain (orchestrator.list_bank_scenarios_for_area)."""

    scenario_id: str
    prompt: str
    title: str | None = None


class SuggestedQuestionOut(BaseModel):
    prompt: str
    notes: str = ""
    scenario_id: str | None = None


class SuggestQuestionsOut(BaseModel):
    """POST /v1/prep-plans/areas/{id}/suggest-questions - preview only,
    nothing persisted. The candidate adds whichever ones they want
    individually (each becomes its own POST .../questions call)."""

    questions: list[SuggestedQuestionOut]


class PrepPlanAreaOut(BaseModel):
    id: str
    plan_id: str
    round_type: str
    label: str
    sort_order: int
    questions: list[PrepPlanQuestionOut] = []


class PrepPlanOut(BaseModel):
    id: str
    name: str
    role_family: str
    level: str
    domain: str
    company_profile: str
    duration_minutes: int
    mode: Literal["text", "voice", "both"]
    created_at: datetime
    updated_at: datetime
    areas: list[PrepPlanAreaOut] = []
