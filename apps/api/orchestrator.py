"""
Orchestrator - the BFF-side glue between apps/api/routes/rounds.py and
src/roundzero/*: gateway selection, the interviewer turn loop, persistence, and
composing the final RoundEvaluation out of evaluation + debrief + improvement
(three separate modules on purpose - see each module's docstring).

Server holds the clock (milestone-1.md step 5): time_remaining_sec is always
computed from started_at, never trusted from client input or drifted by a
per-turn decrement.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from apps.api.models import (
    EvaluationRecord,
    LoopAttempt,
    LoopCommitteeRecord,
    PAYPERLOOP_PLAN,
    PlannedRound,
    PrepPlan,
    PrepPlanArea,
    PrepPlanQuestion,
    RealInterviewExperience,
    RealInterviewOutcome,
    RoundAttempt,
    RoundWorkspaceState,
    TranscriptTurn,
    TRIAL_ROUNDS_INCLUDED,
    TRIAL_WINDOW_DAYS,
    UNSELECTED_PLAN,
    UserEntitlement,
    WorkspaceEvent,
)
from apps.api import worldmodel_service
from apps.api.schemas import (
    AddCustomQuestionIn,
    DimensionScoreDelta,
    HistoryItemOut,
    LoopCreateRequest,
    PredictionSnapshotOut,
    PrepPlanAreaIn,
    PrepPlanIn,
    QuestionProgressOut,
    RealInterviewExperienceIn,
    RealInterviewOutcomeIn,
    RoundComparisonOut,
    StartRoundRequest,
    TimelineEventOut,
)
from roundzero.debrief.committee import CommitteeReport, llm_committee_synthesis, rule_based_committee_synthesis
from roundzero.debrief.real_interview import llm_structure_experience, rule_based_structure_experience
from roundzero.debrief.real_interview import StructuredExperience
from roundzero.prep_plan.suggest import (
    FREEFORM_ROUND_TYPES,
    SuggestedQuestion,
    filter_bank_scenarios,
    llm_suggest_questions,
    scenario_id_of,
    suggest_questions_from_bank,
)
from roundzero.debrief.synthesis import llm_report_synthesis, primary_concern, strengths_and_weaknesses
from roundzero.domain.enums import CoverageStatus, Phase
from roundzero.domain.interview import ConversationState, ConversationTurn, TargetRole
from roundzero.evaluation.evaluator import Evaluator, LLMEvaluator, RuleBasedEvaluator
from roundzero.evaluation.models import RoundEvaluation, ScoredRound
from roundzero.evaluation.rubric_loader import rubric_dimension_keys
from roundzero.improvement.plan import build_improvement_plan
from roundzero.leveling.calibration import LevelCalibration, calibrate_level
from roundzero.interviewers.backend_system_design.agent import BackendSystemDesignInterviewer
from roundzero.interviewers.coding.agent import CodingInterviewer
from roundzero.interviewers.ml_depth.agent import MLDepthInterviewer
from roundzero.interviewers.ml_system_design.agent import MLSystemDesignInterviewer
from roundzero.interviewers.technical_leadership.agent import TechnicalLeadershipInterviewer
from roundzero.interviewers.xfn.agent import XFNInterviewer
from roundzero.llm.gateway import LLMGateway
from roundzero.llm.prompt_loader import load_scenarios
from roundzero.llm.providers.anthropic_provider import AnthropicGateway
from roundzero.llm.providers.fallback_provider import FallbackLLMGateway
from roundzero.llm.providers.gemini_provider import GeminiGateway
from roundzero.llm.providers.mock_provider import MockLLMGateway
from roundzero.llm.providers.openai_provider import OpenAIGateway

ROUND_TYPE = "ml_system_design"
CODING_ROUND_TYPE = "coding"
ML_DEPTH_ROUND_TYPE = "ml_depth"
BACKEND_SYSTEM_DESIGN_ROUND_TYPE = "backend_system_design"
TECHNICAL_LEADERSHIP_ROUND_TYPE = "technical_leadership"
XFN_ROUND_TYPE = "xfn"

# Every round type with a real interviewer today. PlannedRound.round_type can
# be any of the 7 in apps/web/components/RoundTypeIcon.tsx (a loop can be
# planned with all of them, per the user's own call: "let them create with
# all the rounds, but then can start only one"), but start_planned_round only
# ever allows starting one whose key is in this dict. REAL_ROUND_TYPES is
# derived from it, not maintained separately, so the two can never drift -
# and it's a plain dict literal, not admin-editable RoundTypeOption.enabled
# (that flag is display-only for every type except these - see
# RoundTypeOption's docstring in apps/api/models.py) - an admin flipping it
# on for e.g. "system_design" must not make this code think a real
# interviewer exists for it. Only "hiring_manager" remains coming-soon now -
# every other round type in RoundTypeIcon.tsx has a real interviewer.
INTERVIEWERS: dict[str, type] = {
    ROUND_TYPE: MLSystemDesignInterviewer,
    CODING_ROUND_TYPE: CodingInterviewer,
    ML_DEPTH_ROUND_TYPE: MLDepthInterviewer,
    BACKEND_SYSTEM_DESIGN_ROUND_TYPE: BackendSystemDesignInterviewer,
    TECHNICAL_LEADERSHIP_ROUND_TYPE: TechnicalLeadershipInterviewer,
    XFN_ROUND_TYPE: XFNInterviewer,
}
REAL_ROUND_TYPES = frozenset(INTERVIEWERS.keys())

logger = logging.getLogger("roundzero.orchestrator")


class PlannedRoundNotFoundError(Exception):
    """Raised when a planned_round_id doesn't exist or doesn't belong to the
    requesting user - apps/api/routes/loops.py turns this into a 404."""


class PlannedRoundAlreadyStartedError(Exception):
    """Raised when start_planned_round is called twice for the same planned
    round - apps/api/routes/loops.py turns this into a 409."""


class RoundTypeNotAvailableError(Exception):
    """Raised when start_planned_round is called for a round_type outside
    REAL_ROUND_TYPES - apps/api/routes/loops.py turns this into a 400. Not a
    server error: the frontend disables the Start button for these, so
    reaching here means either a stale UI or someone calling the API
    directly - the message reflects that honestly rather than pretending."""


class InterviewerUnavailableError(Exception):
    """Raised when every configured LLM gateway failed to produce a turn (e.g.
    Gemini's free-tier quota exhausted, both Gemini and the Anthropic fallback
    down, or a bare Gemini/Anthropic key with no fallback configured at all).

    orchestrator.create_round()/post_message() are the ONLY two places that
    call interviewer.next_turn() (see module docstring - both text and voice
    transports share this one call), and until this was added, a raw provider
    exception (e.g. google.genai.errors.ClientError) escaped all the way to
    the ASGI server unhandled. That's two problems, not one: (1) a generic,
    unhelpful 500 for the candidate, and (2) Starlette's CORSMiddleware never
    gets a chance to attach CORS headers to a response for an exception that
    propagates past it - so the browser's fetch() rejects with a bare
    "Failed to fetch" TypeError instead of surfacing any real status/detail
    at all (see the 2026-09-01 "Failed to fetch on Voice" investigation,
    which traced back to a Gemini 429 RESOURCE_EXHAUSTED - free-tier is only
    20 requests/day - not anything voice-specific).

    apps/api/routes/rounds.py catches this and turns it into a clean
    HTTPException(503, ...), which - being a normal FastAPI-handled exception
    - CORSMiddleware does wrap properly, so the frontend gets back a real,
    readable error message instead."""


class EvaluationUnavailableError(Exception):
    """Same idea as InterviewerUnavailableError, for submit_round()'s scoring
    path instead of the interviewer's turn-generation path: get_evaluator()
    (LLMEvaluator/GPT-5 mini when OPENAI_API_KEY is set) and
    llm_report_synthesis() (a second, separate OpenAI call) can both fail the
    exact same way Gemini did (rate limits, outages). Without this,
    round_.status had already been committed as "EVALUATING" before either
    call runs, so an unhandled failure here left the round stuck in
    EVALUATING forever with no EvaluationRecord - not just an opaque error,
    a permanently broken round. submit_round() now resets status back to
    "SUBMITTED" before raising this, so calling submit again (once the
    provider recovers) re-enters cleanly instead of being wedged."""


class CommitteeNotReadyError(Exception):
    """Raised by generate_committee_report/get_committee_report when a loop
    doesn't yet qualify for a committee synthesis (specs/002 P0.6) - not every
    real round in the loop has reached EVALUATED yet, or fewer than 2 have.
    apps/api/routes/loops.py turns this into a 400 on POST / 404 on GET, same
    "not an error, just not there yet" honesty as RoundTypeNotAvailableError."""


class CommitteeUnavailableError(Exception):
    """Same idea as EvaluationUnavailableError, for the committee LLM call -
    a transient OpenAI failure during llm_committee_synthesis shouldn't leave
    anything wedged (there's no status field to reset here, since a
    LoopCommitteeRecord is only ever written on success) but should surface as
    a clean 503 rather than an unhandled 500. apps/api/routes/loops.py turns
    this into a 503, same as EvaluationUnavailableError."""


class LinkedLoopNotFoundError(Exception):
    """Raised by create_real_interview_experience when linked_loop_attempt_id
    doesn't exist or doesn't belong to the requesting user (specs/002
    P0.11/P0.12) - apps/api/routes/real_interviews.py turns this into a 404.
    A real interview is never linked to a loop it can't actually verify
    ownership of - see real_interview_prediction's docstring for why a wrong
    link would be worse than no link at all."""


class PlanQuestionNotFoundError(Exception):
    """Raised by start_round_from_plan_question when the given question_id
    doesn't exist, or its area/plan don't belong to the requesting user -
    apps/api/routes/prep_plans.py turns this into a 404. Unlike every other
    Prep Plan mutation below (which follow the get_owned_prep_plan_* -> None
    -> route-level 404 split), starting a round is a single orchestrator
    call with no pre-resolved/owned object to hand in, so it resolves and
    ownership-checks the full plan -> area -> question chain itself and
    raises here rather than returning None."""


class BankScenarioNotFoundError(Exception):
    """Raised by add_prep_plan_question_from_bank when the given scenario_id
    doesn't exist in that area's round_type scenario bank -
    apps/api/routes/prep_plans.py turns this into a 404. Means the frontend
    is showing a stale bank listing, or someone is calling the API directly
    with a made-up id - same "reflects that honestly" spirit as
    RoundTypeNotAvailableError."""


class CustomQuestionNotAllowedError(Exception):
    """Raised by add_custom_prep_plan_question for any area whose round_type
    isn't in prep_plan.suggest.FREEFORM_ROUND_TYPES (today, that means every
    Coding area) - apps/api/routes/prep_plans.py turns this into a 400.
    Coding's workspace needs the structured title/constraints/entry_point/
    starter_code/test_cases fields a freeform candidate-typed prompt has no
    way to supply (see PrepPlanQuestion's docstring, apps/api/models.py) -
    rejecting this up front means there is no way to end up with a Coding
    question that can't actually run a round."""


class DrillSourceNotFoundError(Exception):
    """Raised by start_drill_round when the source round either doesn't
    exist/isn't owned by this user, hasn't been evaluated yet (no
    EvaluationRecord), or the requested priority doesn't match any of that
    evaluation's improvement_plan items - apps/api/routes/rounds.py turns
    this into a 404. "Practice this weakness" only ever appears next to an
    already-rendered improvement plan item on the report page, so any of
    these should only happen if the round was deleted or re-evaluated
    between page load and the click, or someone calls the API directly with
    a stale priority."""

class InsufficientQuotaError(Exception):
    """Raised by _require_quota (called from create_loop, sized to the number
    of rounds requested, and from _start_round itself, sized to 1 - the two
    pre-flight enforcement points, see UserEntitlement's docstring in
    apps/api/models.py) when the caller doesn't have enough rounds left on
    their current plan, or their free trial has expired. apps/api/routes/
    rounds.py, loops.py and prep_plans.py all turn this into a 402 Payment
    Required - not a 400, since the request itself is well-formed, the
    problem is the account's remaining balance."""


class PlanNotAvailableError(Exception):
    """Raised by select_plan for any plan other than "none" - see its
    docstring. apps/api/routes/auth.py turns this into a 400."""


def get_gateway(*, interviewer_turn_count: int = 0) -> LLMGateway:
    """Locked V1 stack: GEMINI_API_KEY present -> GeminiGateway (Gemini 3.6 Flash
    interviewer - see src/roundzero/llm/providers/gemini_provider.py's docstring
    for the 2.5 -> 3.6 model bump). Otherwise ANTHROPIC_API_KEY -> AnthropicGateway
    (kept working but no longer the default provider now that the stack is
    locked to Gemini - see the "Lock it" conversation, tasks.md). Otherwise
    MockLLMGateway, fast-forwarded to interviewer_turn_count so a request
    mid-round picks up where the script left off (mock_provider.py's start_turn
    docstring).

    Fallback priority when GEMINI_API_KEY is present (2026-09-29, DOG-001 -
    live dogfooding hit the Gemini interviewer's rate limit routinely, not
    just during outages, and DOG-007 showed a candidate's answer is lost
    outright when that call fails with no fallback configured):
    OPENAI_API_KEY first if set - GPT-5 mini (ROUNDZERO_OPENAI_MODEL) is both
    cost-conscious (explicit product call: cost matters here) and a model
    already validated in this codebase, just for evaluation rather than
    interviewing. Using it as the interviewer's fallback too means a Gemini
    outage round is graded by the same vendor that asked the question for
    that one turn - a narrower version of the vendor-separation concern
    OpenAIGateway's own docstring raises for the *evaluator* pick - accepted
    here as a deliberate tradeoff since it only applies to the turns Gemini
    itself failed on, not the round as a whole, and the alternative is losing
    the candidate's answer entirely (DOG-007). ANTHROPIC_API_KEY remains the
    fallback when OpenAI isn't configured (2026-09-01: Gemini returned a
    transient "503 - high demand" during a live voice round, stalling both
    the text and voice paths since they share this same call) - either way, a
    Gemini failure no longer stalls the interview outright, it quietly
    retries on the fallback for that turn."""
    if os.environ.get("GEMINI_API_KEY") and os.environ.get("OPENAI_API_KEY"):
        return FallbackLLMGateway(GeminiGateway(), OpenAIGateway())
    if os.environ.get("GEMINI_API_KEY") and os.environ.get("ANTHROPIC_API_KEY"):
        return FallbackLLMGateway(GeminiGateway(), AnthropicGateway())
    if os.environ.get("GEMINI_API_KEY"):
        return GeminiGateway()
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicGateway()
    return MockLLMGateway(start_turn=interviewer_turn_count)


def get_evaluator() -> Evaluator:
    """Locked V1 stack: OPENAI_API_KEY present -> LLMEvaluator (GPT-5 mini).
    Otherwise RuleBasedEvaluator - see that class's docstring for why scoring
    with a mock LLM would be theater rather than degrading to something honest."""
    if os.environ.get("OPENAI_API_KEY"):
        return LLMEvaluator(OpenAIGateway())
    return RuleBasedEvaluator()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def time_remaining_sec(round_: RoundAttempt) -> int:
    if round_.started_at is None:
        return round_.duration_minutes * 60
    started_at = round_.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    elapsed = (_now() - started_at).total_seconds()
    return max(0, round(round_.duration_minutes * 60 - elapsed))


def _workspace_context(db: DBSession, round_id: str, round_type: str = ROUND_TYPE) -> str | None:
    """The interviewer's read-only view of the workspace panel. ml_system_design
    gets the client-computed canvas_summary (see lib/workspace/summarizeScene.ts),
    never the raw Excalidraw scene JSON. Coding has no canvas - it gets the raw
    code_text buffer instead (see CodingInterviewer._build_user_message's
    docstring for why that's honest rather than a "summary" of something that
    doesn't need summarizing). None until the round's first workspace autosave
    lands, for either kind."""
    state = db.get(RoundWorkspaceState, round_id)
    if state is None:
        return None
    if round_type == CODING_ROUND_TYPE:
        return state.code_text
    return state.canvas_summary


def _latest_coding_test_result(db: DBSession, round_id: str) -> str | None:
    """Most recent Run-button result for this round (WorkspaceEvent
    kind="test_result", written by POST /{round_id}/workspace/run), formatted
    the same compact way roundzero.coding.feedback._build_user_message already
    formats it for the separate code-quality-feedback panel.

    Closes a real gap found during a live UX pass (2026-09-03):
    CodingInterviewer._build_user_message's own comment used to say "today's
    Run button result isn't threaded back into this call" - which quietly
    made prompts/interviewers/coding/v1.md's "you are given ... the real test
    results" claim false. The chat interviewer (Ava) could never actually see
    whether the candidate's code passed, so it could never react to a run the
    way a real interviewer watching your screen would ("nice, all passing -
    what's the complexity here?" / "looks like the empty-input case is
    failing"). A separate, disconnected feedback panel already did react to
    runs (see roundzero.coding.feedback.generate_code_feedback), but that is
    a one-shot static report, not part of the actual back-and-forth
    conversation - this makes the conversation itself aware, on top of that,
    not instead of it."""
    event = (
        db.query(WorkspaceEvent)
        .filter(WorkspaceEvent.round_id == round_id, WorkspaceEvent.kind == "test_result")
        .order_by(WorkspaceEvent.created_at.desc())
        .first()
    )
    if event is None:
        return None
    results = (event.payload or {}).get("test_results") or []
    if not results:
        return None
    lines = "\n".join(
        f"- {r.get('name')}: "
        + ("PASSED" if r.get("passed") is True else "FAILED" if r.get("passed") is False else "NOT RUN")
        + (f" (output/error: {r['actual_output']})" if r.get("actual_output") else "")
        for r in results
    )
    passed = sum(1 for r in results if r.get("passed") is True)
    return f"Most recent Run result ({passed}/{len(results)} tests passing):\n{lines}"


def _default_coverage_for(round_type: str) -> dict[str, CoverageStatus]:
    """A round's coverage map must start with exactly that round's own rubric
    dimensions (rubrics/{round_type}/v1.yaml via rubric_dimension_keys), not
    ml_system_design's - domain.interview.default_coverage() is hardcoded to
    the ml_system_design-specific RUBRIC_DIMENSIONS global and is only correct
    for that one round type, so this is the round-type-aware equivalent used
    everywhere a round starts."""
    return {dim: CoverageStatus.NOT_COVERED for dim in rubric_dimension_keys(round_type)}


# Scenario dict keys (beyond "prompt"/"id"/"name") that get carried onto
# RoundAttempt.scenario_meta when present - the structured fields Coding's
# workspace needs to render the real problem (title/constraints/entry_point/
# starter code/tests) instead of CodingWorkspace.tsx's old hardcoded
# placeholder. ml_system_design's scenarios don't have most of these keys, so
# for that round type scenario_meta ends up {} (falsy) rather than None -
# harmless, and kept as {} rather than skipped so callers never have to
# distinguish "no meta collected" from "collection returned nothing".
_SCENARIO_META_KEYS = (
    "title",
    "constraints",
    "entry_point",
    "starter_code_python",
    "test_cases",
)


def _scenario_meta(scenario: dict) -> dict:
    return {k: scenario[k] for k in _SCENARIO_META_KEYS if k in scenario}


_UNPROVISIONED_ROUNDS = 1_000_000  # see get_entitlement_status's "entitlement is None" branch


@dataclass
class EntitlementStatus:
    """Live snapshot of a user's round quota - what both the pre-flight
    enforcement checks below and GET /v1/auth/me's response are built from.
    See UserEntitlement's docstring in apps/api/models.py for the underlying
    row this is computed from."""

    cohort: str
    plan: str
    billing_interval: str
    rounds_included: int
    rounds_used: int
    rounds_remaining: int
    current_period_start: datetime
    expires_at: datetime | None
    is_expired: bool


def get_entitlement_status(db: DBSession, user_id: str) -> EntitlementStatus:
    """rounds_used is computed live by counting every RoundAttempt this user
    has created since current_period_start - including abandoned/incomplete
    ones. Starting a round is what incurs the LLM cost this whole system
    exists to meter (see _start_round), not finishing it, so an abandoned
    round still counts against quota. Never stored redundantly on
    UserEntitlement itself - same "compute at read time" discipline as
    real_interview_prediction and PrepPlanQuestion progress.

    DOG-004 (user decision, 2026-09-29, ahead of inviting the first real
    testers): a round that reaches EvaluationRecord.not_assessed=True never
    actually recorded an interview - the candidate never got a real answer
    saved, whether because they abandoned immediately or (DOG-007) an
    interviewer LLM call failed and silently dropped what they typed. Either
    way there's no interview to show for it, so it's excluded from
    rounds_used below - refunded the moment submit_round evaluates it as
    not_assessed, not before (a round still ACTIVE/in progress keeps
    counting, same as always, since it may yet become a real interview and
    has likely already incurred at least the opening LLM turn's cost).
    Deliberately not narrower than that (e.g. only refunding the specific
    "LLM call failed" case) - distinguishing "candidate never answered" from
    "an answer was lost to a failure" isn't something the data model
    captures today, and at this stage (a handful of invited testers, not
    open signup) the abuse surface of a free retry on a truly empty round
    is negligible next to the cost of a tester losing quota to a bug that
    isn't their fault."""
    entitlement = db.query(UserEntitlement).filter(UserEntitlement.user_id == user_id).first()
    now = _now()
    if entitlement is None:
        # In real traffic this never happens - apps/api/deps.py::
        # get_current_user provisions an entitlement row for every user
        # before any route handler (and therefore any of this module's
        # round-starting functions) ever runs. This branch only exists for
        # callers that reach the orchestrator directly without going through
        # that dependency - unit tests and one-off scripts using a synthetic
        # user_id that was never provisioned. Since such a caller was never
        # meant to be quota-limited in the first place (it isn't a real
        # signed-up user going through the app), degrade to "effectively
        # unlimited" rather than blocking it - the opposite failure mode
        # (a real user silently ungated) can't occur here precisely because
        # deps.py always provisions first.
        return EntitlementStatus(
            cohort="unprovisioned",
            plan="none",
            billing_interval="none",
            rounds_included=_UNPROVISIONED_ROUNDS,
            rounds_used=0,
            rounds_remaining=_UNPROVISIONED_ROUNDS,
            current_period_start=now,
            expires_at=None,
            is_expired=False,
        )
    not_assessed_round_ids = db.query(EvaluationRecord.round_id).filter(EvaluationRecord.not_assessed.is_(True))
    rounds_used = (
        db.query(RoundAttempt)
        .filter(
            RoundAttempt.user_id == user_id,
            RoundAttempt.created_at >= entitlement.current_period_start,
            RoundAttempt.id.notin_(not_assessed_round_ids),
        )
        .count()
    )
    expires_at = entitlement.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        # SQLite (unlike Postgres) hands back naive datetimes regardless of
        # what was stored - same fixup as time_remaining_sec above.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    is_expired = expires_at is not None and expires_at <= now
    return EntitlementStatus(
        cohort=entitlement.cohort,
        plan=entitlement.plan,
        billing_interval=entitlement.billing_interval,
        rounds_included=entitlement.rounds_included,
        rounds_used=rounds_used,
        rounds_remaining=max(0, entitlement.rounds_included - rounds_used),
        current_period_start=entitlement.current_period_start,
        expires_at=entitlement.expires_at,
        is_expired=is_expired,
    )


def _require_quota(db: DBSession, user_id: str, needed: int) -> None:
    """Pre-flight quota check (design doc: "check upfront, sized to what's
    being scheduled, not lazily round-by-round"). Two call sites: create_loop
    below, sized to len(req.rounds) (planning a loop costs nothing itself,
    but there's no point letting someone plan more rounds than they could
    ever start), and _start_round itself, sized to 1 - the true point of
    LLM cost, and the hard backstop even if create_loop's softer check was
    somehow bypassed (e.g. an old planned round from before a downgrade)."""
    entitlement_status = get_entitlement_status(db, user_id)
    if entitlement_status.plan == UNSELECTED_PLAN:
        # Subscribe gate (UserEntitlement's docstring) - a brand-new
        # self-signup user has 0 rounds until they explicitly pick a plan.
        # Distinguished from "expired"/"exhausted" below so the frontend
        # can send them to Subscribe rather than an upgrade prompt that
        # implies they once had something to run out of.
        raise InsufficientQuotaError("Pick a plan to get started - even the free one only takes a click.")
    if entitlement_status.is_expired:
        raise InsufficientQuotaError(
            "Your free trial has ended. Upgrade to a paid plan to keep scheduling interviews."
        )
    if entitlement_status.rounds_remaining < needed:
        if needed > 1:
            raise InsufficientQuotaError(
                f"You have {entitlement_status.rounds_remaining} round(s) left - not enough for a "
                f"full loop of {needed}. Buy more, upgrade, or start an individual round instead."
            )
        raise InsufficientQuotaError(
            "You're out of interview rounds on your current plan. Upgrade to keep practicing."
        )


_SELECTABLE_PLANS = frozenset({"none"})  # only the free plan is implemented - see select_plan's docstring


def select_plan(db: DBSession, user_id: str, plan: str) -> EntitlementStatus:
    """The Subscribe step (UserEntitlement's docstring, "Subscribe gate"
    paragraph) - POST /v1/auth/subscribe calls this. A brand-new self-signup
    user's entitlement starts at plan=UNSELECTED_PLAN, 0 rounds
    (apps/api/deps.py::_ensure_entitlement) - nothing to practice with until
    they explicitly pick a plan here, on apps/web's /upgrade page. Picking
    "none" is what actually grants the free trial, and its 7-day window
    starts now (when it was claimed), not back at signup - a deliberate
    improvement over measuring the window from signup regardless of whether
    the person ever came back to claim it.

    Only "none" is implemented - every paid plan needs Stripe (pricing-
    design.md Phase 2/3, not built yet), so selecting one raises
    PlanNotAvailableError. The frontend's Subscribe page already shows those
    cards disabled/"Coming soon"; this is the backend backstop, not the
    primary UX for that case."""
    if plan not in _SELECTABLE_PLANS:
        raise PlanNotAvailableError(f"The '{plan}' plan isn't available yet - check back soon.")

    entitlement = db.query(UserEntitlement).filter(UserEntitlement.user_id == user_id).first()
    if entitlement is None:
        # Shouldn't happen - apps/api/deps.py::get_current_user always
        # provisions one first - but create it here rather than 500ing if
        # it's somehow missing.
        entitlement = UserEntitlement(user_id=user_id, cohort="normal")
        db.add(entitlement)

    now = _now()
    entitlement.plan = "none"
    entitlement.rounds_included = TRIAL_ROUNDS_INCLUDED
    entitlement.current_period_start = now
    entitlement.expires_at = now + timedelta(days=TRIAL_WINDOW_DAYS)
    db.commit()
    return get_entitlement_status(db, user_id)


def credit_purchase(db: DBSession, user_id: str, rounds_purchased: int) -> EntitlementStatus:
    """Called by apps/api/routes/billing.py's webhook handler once a Stripe
    Pay-per-loop Checkout Session is confirmed paid (checkout.session.
    completed - see that module's docstring for the idempotency guard around
    this call). Purchased rounds never expire and aren't tied to a recurring
    period, unlike the free-trial/subscription rounds this entitlement row
    otherwise tracks (UserEntitlement's docstring) - so completing a purchase
    "graduates" the account: rounds_included goes up by what was bought,
    expires_at is cleared (a still-ticking free-trial deadline shouldn't
    apply to rounds someone just paid real money for), and cohort flips to
    "paid". plan only moves to PAYPERLOOP_PLAN when it isn't already
    something better - a Monthly/Yearly/Founding subscriber (Phase 3, not
    built yet) buying a top-up pack keeps their subscription's plan name,
    not "payperloop"."""
    entitlement = db.query(UserEntitlement).filter(UserEntitlement.user_id == user_id).first()
    if entitlement is None:
        # Shouldn't happen (apps/api/deps.py always provisions one first),
        # but create it here rather than losing a paid purchase to a missing
        # row.
        entitlement = UserEntitlement(user_id=user_id, cohort="paid", plan=PAYPERLOOP_PLAN, rounds_included=0)
        db.add(entitlement)
        db.flush()

    entitlement.rounds_included = entitlement.rounds_included + rounds_purchased
    entitlement.cohort = "paid"
    if entitlement.plan in (UNSELECTED_PLAN, "none"):
        entitlement.plan = PAYPERLOOP_PLAN
    entitlement.expires_at = None
    db.commit()
    return get_entitlement_status(db, user_id)


def _start_round(
    db: DBSession,
    user_id: str,
    loop_attempt_id: str,
    *,
    round_type: str,
    role_family: str,
    level: str,
    domain: str,
    company_profile: str,
    duration_minutes: int,
    mode: str,
    scenario_override: dict | None = None,
    prep_plan_question_id: str | None = None,
    drill_focus_hint: str | None = None,
) -> tuple[RoundAttempt, TranscriptTurn]:
    """The actual "start" work - pick a scenario, create the RoundAttempt row,
    call the real interviewer for its opening turn, persist that turn. Shared
    by create_round (the original single-round /v1/rounds path, which creates
    its own fresh loop, ml_system_design only), start_planned_round (starts
    one round of an already-created loop, any round_type in REAL_ROUND_TYPES),
    and start_round_from_plan_question (user-pitched Prep Plans feature) -
    all three converge here since starting a round means the exact same thing
    either way, just with the loop already existing in some cases, which
    round type varying, and now which scenario varying too. Callers are
    responsible for checking round_type is in REAL_ROUND_TYPES before calling
    this, it's not re-checked here.

    `scenario_override`, when given, is used verbatim instead of calling
    interviewer.pick_scenario() - this is what lets a Prep Plan question
    (either a specific bank scenario looked up by id, or a candidate's own
    freeform prompt) start a round against exactly that scenario rather than
    a random one. `prep_plan_question_id` is stamped onto the created round
    whenever a plan question was the source, so that question's progress can
    be computed later by querying RoundAttempt - see
    orchestrator._question_progress. `drill_focus_hint`, when given
    (user-pitched Drills feature - "Practice this weakness" on a past
    round's report), is stamped onto the created round and passed to the
    interviewer's opening turn as focus_hint (see
    interviewers/*/agent.py's next_turn) so it probes that competency
    harder across the whole round - see orchestrator.start_drill_round."""
    _require_quota(db, user_id, 1)

    target_role = TargetRole(
        role_family=role_family,
        level=level,
        domain=domain,
        company_profile=company_profile,
    )

    interviewer_cls = INTERVIEWERS[round_type]
    interviewer = interviewer_cls(get_gateway(interviewer_turn_count=0))
    if scenario_override is not None:
        scenario = scenario_override
    else:
        # Avoid handing the candidate the exact same scenario two attempts in a row -
        # look at their last few rounds of this same round_type (any modality/status)
        # and keep pick_scenario() from choosing those ids again (tasks.md item 4's
        # "avoid repeats across attempts" note, now that there are 10+ seeds to pick
        # from - see MLSystemDesignInterviewer.pick_scenario's docstring, which
        # CodingInterviewer.pick_scenario mirrors exactly).
        recent_scenario_ids = frozenset(
            row[0]
            for row in db.query(RoundAttempt.scenario_id)
            .filter(RoundAttempt.user_id == user_id, RoundAttempt.round_type == round_type)
            .order_by(RoundAttempt.created_at.desc())
            .limit(5)
            .all()
            if row[0]
        )
        scenario = interviewer.pick_scenario(target_role, exclude_ids=recent_scenario_ids)

    round_ = RoundAttempt(
        loop_attempt_id=loop_attempt_id,
        user_id=user_id,
        round_type=round_type,
        modality=mode,
        role_family=role_family,
        level=level,
        domain=domain,
        company_profile=company_profile,
        duration_minutes=duration_minutes,
        scenario_id=scenario.get("id", scenario.get("name", "seed_1")),
        scenario_prompt=scenario["prompt"],
        scenario_meta=_scenario_meta(scenario),
        status="ACTIVE",
        phase=Phase.INTRO.value,
        coverage={},
        started_at=_now(),
        prep_plan_question_id=prep_plan_question_id,
        drill_focus_hint=drill_focus_hint,
    )
    db.add(round_)
    db.flush()

    state = ConversationState(
        phase=Phase.INTRO,
        time_remaining_sec=duration_minutes * 60,
        coverage=_default_coverage_for(round_type),
    )
    coding_kwargs = (
        {"test_result_context": _latest_coding_test_result(db, round_.id)} if round_type == CODING_ROUND_TYPE else {}
    )
    try:
        output = interviewer.next_turn(
            scenario=scenario,
            state=state,
            candidate_message=None,
            target_role=target_role,
            workspace_context=_workspace_context(db, round_.id, round_type),
            voice_mode=round_.modality in ("voice", "both"),
            focus_hint=drill_focus_hint,
            **coding_kwargs,
        )
    except Exception as exc:
        logger.exception("Interviewer failed to produce the opening turn for round_id=%s", round_.id)
        raise InterviewerUnavailableError(
            "The interviewer's AI backend is temporarily unavailable (rate limited or having an "
            "outage) - please try again in a moment."
        ) from exc

    round_.phase = output.phase.value
    round_.coverage = {k: v.value for k, v in output.coverage.items()}

    turn = TranscriptTurn(
        round_id=round_.id,
        turn_index=0,
        speaker="interviewer",
        text=output.utterance,
        phase=output.phase.value,
        competency_tags=output.competency_tags,
    )
    db.add(turn)
    db.commit()
    db.refresh(round_)
    db.refresh(turn)
    return round_, turn


# Slug words that are abbreviations/acronyms, not ordinary words -
# str.capitalize() only capitalizes the first letter and lowercases the
# rest, so "ml" becomes "Ml", not "ML". That lowercase "l" is visually
# indistinguishable from a capital "I" in every sans-serif UI font (neither
# has a foot/serif), so "Ml Engineer" reads as "MI Engineer" - a real text
# bug, not a font-rendering one. Extend this map if a future role/level/
# company slug introduces another all-caps abbreviation.
_LABEL_WORD_OVERRIDES = {"ml": "ML"}


def _title_word(word: str) -> str:
    return _LABEL_WORD_OVERRIDES.get(word, word.capitalize())


def _derive_auto_name(
    db: DBSession, user_id: str, role_family: str, level: str, company_profile: str, *, prefix: str
) -> str:
    """Shared "{Level} {Role}[ at Company] {Kind}[ #N]" name generator
    (user request, reworked 2026-09-29 for a cleaner, non-debug-looking
    format - see below) - used both for a loop auto-created via the
    original single-round /v1/rounds path (create_round below,
    prefix="Practice", since /setup never asks for a name at all), a
    pre-filled still-editable suggestion for the deliberate loop builder's
    free-text name field (/loops/new, prefix="Loop" - see suggest_loop_name
    below; that field stays real free text, e.g. "Google-Staff -MLE", this
    is only a starting point), a round started from a prep-plan question
    (prefix="Plan", displayed as "Prep Plan" so it reads as English rather
    than a raw slug), and a "practice this weakness" drill round
    (prefix="Drill").

    Originally packed prefix + company + role/level + an MMDDYY date stamp
    + a mandatory sequence number into one string (e.g.
    "Plan-Generic - Staff ML Engineer-092926-3") - technically unique and
    collision-free, but it read like debug/log output, not a name a
    professional product would show (flagged in a 2026-09-29 look-and-feel
    pass). Two problems beyond raw appearance: the date was already shown a
    second time right next to the name everywhere it's rendered (see
    LoopCard's own created_at line in apps/web/components/loops/
    LoopList.tsx), and every single loop got a numeric suffix starting at
    "-1" even the first time that role/level/company combo was ever used,
    when only a genuine repeat needs to be disambiguated at all.

    New format: "{Level} {Role} {Kind}[ at {Company}]", with a "generic"
    company_profile (the default/no-specific-company choice) omitted
    rather than rendered as "at Generic" - same convention
    ConversationContext.describe_target already uses for the same reason
    (src/roundzero/domain/interview.py). No date, since the surrounding UI
    already shows one. A " #N" suffix is appended only from the second
    occurrence onward (still this user's own count, still scoped
    separately per prefix/kind, still deterministic and collision-free -
    just invisible until it's actually disambiguating something, so "first
    one like this" reads as a normal name instead of always ending in a
    stray "-1")."""
    label = " ".join(_title_word(w) for w in f"{level}_{role_family}".split("_"))
    kind = "Prep Plan" if prefix == "Plan" else prefix
    base = f"{label} {kind}"
    if company_profile and company_profile != "generic":
        company_label = " ".join(_title_word(w) for w in company_profile.split("_"))
        base = f"{base} at {company_label}"
    existing = db.query(LoopAttempt).filter(
        LoopAttempt.user_id == user_id,
        or_(LoopAttempt.name == base, LoopAttempt.name.like(f"{base} #%")),
    ).count()
    return base if existing == 0 else f"{base} #{existing + 1}"


def _derive_loop_name(db: DBSession, user_id: str, role_family: str, level: str, company_profile: str) -> str:
    """Auto-name for a loop created via the original single-round /v1/rounds
    path (create_round below), which never asked the candidate for a name.
    See _derive_auto_name's docstring for the full naming rationale."""
    return _derive_auto_name(db, user_id, role_family, level, company_profile, prefix="Practice")


def suggest_loop_name(db: DBSession, user_id: str, role_family: str, level: str, company_profile: str) -> str:
    """Suggested starting point for the loop builder's free-text name field
    (GET /v1/loops/suggested-name) - same naming scheme as Practice rounds
    but prefixed "Loop-" and counted separately, since the builder's field
    stays real, editable free text (e.g. "Google-Staff -MLE"), never
    auto-applied without the person seeing/being able to change it first."""
    return _derive_auto_name(db, user_id, role_family, level, company_profile, prefix="Loop")


def create_round(db: DBSession, user_id: str, req: StartRoundRequest) -> tuple[RoundAttempt, TranscriptTurn]:
    """Original single-round entrypoint (POST /v1/rounds, used by /setup's
    quick "Start Interview" flow) - creates its own fresh one-round loop, same
    behavior as before the Loop Planner (create_loop/start_planned_round
    below) existed. Also writes a matching PlannedRound so this round is
    wrapped exactly like one created via the new loop-builder flow - every
    RoundAttempt has exactly one PlannedRound, no special-casing needed
    elsewhere (see PlannedRound's docstring in apps/api/models.py).

    round_type now comes from the request (default ml_system_design) rather
    than being hardcoded - Coding candidate feedback (2026-09-03): Coding
    already has a real interviewer/rubric/workspace, same REAL_ROUND_TYPES
    gate start_planned_round uses below, just never wired into this
    standalone-round entrypoint until now."""
    if req.round_type not in REAL_ROUND_TYPES:
        available = ", ".join(sorted(REAL_ROUND_TYPES))
        raise RoundTypeNotAvailableError(
            f"'{req.round_type}' doesn't have a real interviewer yet - only {available} "
            "can be started today."
        )

    loop_attempt = LoopAttempt(
        user_id=user_id,
        name=_derive_loop_name(db, user_id, req.role_family, req.level, req.company_profile),
    )
    db.add(loop_attempt)
    db.flush()

    round_, turn = _start_round(
        db,
        user_id,
        loop_attempt.id,
        round_type=req.round_type,
        role_family=req.role_family,
        level=req.level,
        domain=req.domain,
        company_profile=req.company_profile,
        duration_minutes=req.duration_minutes,
        mode=req.mode,
    )

    planned = PlannedRound(
        loop_attempt_id=loop_attempt.id,
        user_id=user_id,
        round_type=req.round_type,
        role_family=req.role_family,
        level=req.level,
        domain=req.domain,
        company_profile=req.company_profile,
        duration_minutes=req.duration_minutes,
        modality=req.mode,
        sort_order=0,
        round_attempt_id=round_.id,
    )
    db.add(planned)
    db.commit()

    return round_, turn


def create_loop(db: DBSession, user_id: str, req: LoopCreateRequest) -> LoopAttempt:
    """Real multi-round Loop Planner (specs/002 P0.1): creates the loop and
    every planned round up front, all in one step (per the user's own call -
    "loop and interviews will create together"). Deliberately does NOT call
    the interviewer for any of them - planning a round is not starting it,
    and starting means a real LLM call for an opening turn (see
    _start_round) that shouldn't happen just because a round
    type was included in the plan. The candidate starts each one separately
    via start_planned_round (only round types in REAL_ROUND_TYPES can actually
    be started)."""
    _require_quota(db, user_id, len(req.rounds))

    loop_attempt = LoopAttempt(user_id=user_id, name=req.name)
    db.add(loop_attempt)
    db.flush()

    for i, r in enumerate(req.rounds):
        db.add(
            PlannedRound(
                loop_attempt_id=loop_attempt.id,
                user_id=user_id,
                round_type=r.round_type,
                role_family=req.role_family,
                level=req.level,
                domain=req.domain,
                company_profile=req.company_profile,
                duration_minutes=r.duration_minutes,
                modality=req.mode,
                sort_order=i,
            )
        )
    db.commit()
    db.refresh(loop_attempt)
    return loop_attempt


def list_loops(db: DBSession, user_id: str) -> list[LoopAttempt]:
    return db.query(LoopAttempt).filter(LoopAttempt.user_id == user_id).order_by(LoopAttempt.created_at.desc()).all()


def list_planned_rounds(db: DBSession, loop_attempt_id: str) -> list[PlannedRound]:
    return (
        db.query(PlannedRound)
        .filter(PlannedRound.loop_attempt_id == loop_attempt_id)
        .order_by(PlannedRound.sort_order)
        .all()
    )


def delete_loop(db: DBSession, loop: LoopAttempt) -> None:
    """Deletes a loop and everything under it - every planned round, and for
    any that were actually started, that round's full history (transcript,
    workspace state/events, evaluation), plus the loop's own committee
    synthesis record if one exists (specs/002 P0.6 - added alongside the
    committee feature so it doesn't become the next orphaned-row gap this
    docstring already warns about). A loop is the top-level unit a candidate
    creates (apps/api/routes/loops.py POST /v1/loops); deleting it is meant
    to remove it completely rather than leave orphaned rows behind for
    anything created under it. Ownership is checked by the caller
    (apps/api/routes/loops.py::_get_owned_loop) before this runs - this
    function trusts the LoopAttempt it's given."""
    for planned in list_planned_rounds(db, loop.id):
        if planned.round_attempt_id is not None:
            round_id = planned.round_attempt_id
            db.query(TranscriptTurn).filter(TranscriptTurn.round_id == round_id).delete()
            db.query(WorkspaceEvent).filter(WorkspaceEvent.round_id == round_id).delete()
            db.query(RoundWorkspaceState).filter(RoundWorkspaceState.round_id == round_id).delete()
            db.query(EvaluationRecord).filter(EvaluationRecord.round_id == round_id).delete()
            db.query(RoundAttempt).filter(RoundAttempt.id == round_id).delete()
        db.delete(planned)
    db.query(LoopCommitteeRecord).filter(LoopCommitteeRecord.loop_attempt_id == loop.id).delete()
    db.delete(loop)
    db.commit()


def start_planned_round(db: DBSession, user_id: str, planned_round_id: str) -> tuple[RoundAttempt, TranscriptTurn]:
    planned = db.get(PlannedRound, planned_round_id)
    if planned is None or planned.user_id != user_id:
        raise PlannedRoundNotFoundError(f"Planned round {planned_round_id} not found")
    if planned.round_attempt_id is not None:
        raise PlannedRoundAlreadyStartedError("This round has already been started")
    if planned.round_type not in REAL_ROUND_TYPES:
        available = ", ".join(sorted(REAL_ROUND_TYPES))
        raise RoundTypeNotAvailableError(
            f"'{planned.round_type}' doesn't have a real interviewer yet - only {available} "
            "can be started today."
        )

    round_, turn = _start_round(
        db,
        user_id,
        planned.loop_attempt_id,
        round_type=planned.round_type,
        role_family=planned.role_family,
        level=planned.level,
        domain=planned.domain,
        company_profile=planned.company_profile,
        duration_minutes=planned.duration_minutes,
        mode=planned.modality,
    )

    planned.round_attempt_id = round_.id
    db.commit()
    return round_, turn


def load_transcript(db: DBSession, round_id: str) -> list[TranscriptTurn]:
    return (
        db.query(TranscriptTurn)
        .filter(TranscriptTurn.round_id == round_id)
        .order_by(TranscriptTurn.turn_index)
        .all()
    )


def _workspace_event_summary(event: WorkspaceEvent) -> str:
    """Human-readable one-line summary for a WorkspaceEvent on the Interview
    Replay timeline (get_round_timeline below). WorkspaceEvent rows never
    store a full code/canvas snapshot (see that model's docstring - only
    RoundWorkspaceState, overwritten in place, holds the current one), so
    this is honestly built from the light metadata each event actually
    carries, not a reconstruction of what the code/canvas looked like."""
    payload = event.payload or {}
    if event.kind == "code_change":
        lang = payload.get("code_language", "code")
        return f"Edited {lang} ({payload.get('code_length', 0)} chars)"
    if event.kind == "run_attempt":
        lang = payload.get("language", "code")
        return f"Ran {lang} ({payload.get('code_length', 0)} chars)"
    if event.kind == "test_result":
        results = payload.get("test_results", [])
        passed = sum(1 for r in results if r.get("passed") is True)
        return f"Tests: {passed}/{len(results)} passed"
    if event.kind == "canvas_change":
        summary = payload.get("canvas_summary") or "diagram"
        return f"Canvas updated - {payload.get('element_count', 0)} elements ({summary})"
    return event.kind


def get_round_timeline(db: DBSession, round_id: str) -> list[TimelineEventOut]:
    """Interview Replay (backlog P0.9 - "OK to start with transcript +
    code/canvas timeline before full synced audio replay"). Merges
    TranscriptTurn and WorkspaceEvent rows into one chronological list by
    created_at - both already carried real timestamps, they just were never
    exposed together (see TimelineEventOut's docstring, apps/api/schemas.py).
    No new tables, no new columns - this is entirely a read over data the
    round-in-progress endpoints (post_message, save_code, save_canvas,
    run_code) were already writing."""
    turns = load_transcript(db, round_id)
    events = (
        db.query(WorkspaceEvent)
        .filter(WorkspaceEvent.round_id == round_id)
        .order_by(WorkspaceEvent.created_at)
        .all()
    )
    items = [
        TimelineEventOut(kind=f"turn:{t.speaker}", text=t.text, phase=t.phase, created_at=t.created_at)
        for t in turns
    ] + [
        TimelineEventOut(kind=e.kind, text=_workspace_event_summary(e), phase=None, created_at=e.created_at)
        for e in events
    ]
    items.sort(key=lambda i: i.created_at)
    return items


def post_message(db: DBSession, round_: RoundAttempt, text: str) -> TranscriptTurn:
    turns = load_transcript(db, round_.id)
    interviewer_turn_count = sum(1 for t in turns if t.speaker == "interviewer")

    state = ConversationState(
        phase=Phase(round_.phase),
        time_remaining_sec=time_remaining_sec(round_),
        coverage={k: CoverageStatus(v) for k, v in round_.coverage.items()},
        turns=[
            ConversationTurn(speaker=t.speaker, text=t.text, phase=Phase(t.phase))
            for t in turns
        ],
    )

    interviewer_cls = INTERVIEWERS.get(round_.round_type, MLSystemDesignInterviewer)
    interviewer = interviewer_cls(get_gateway(interviewer_turn_count=interviewer_turn_count))
    scenario = {"prompt": round_.scenario_prompt, **(round_.scenario_meta or {})}
    # Personalization gap fix (specs/002, 2026-09-03): the RoundAttempt already
    # carries its own role/level/domain/company columns (set once at start,
    # never changed mid-round), so this is a straight passthrough - no new
    # state, just finally handing the interviewer what it already had.
    target_role = TargetRole(
        role_family=round_.role_family,
        level=round_.level,
        domain=round_.domain,
        company_profile=round_.company_profile,
    )
    coding_kwargs = (
        {"test_result_context": _latest_coding_test_result(db, round_.id)}
        if round_.round_type == CODING_ROUND_TYPE
        else {}
    )
    # World-model live steering (specs/005) - None unless ROUNDZERO_WM_ADAPTIVE=live.
    probe_hint = worldmodel_service.current_probe_hint(db, round_)
    try:
        output = interviewer.next_turn(
            scenario=scenario,
            state=state,
            candidate_message=text,
            target_role=target_role,
            workspace_context=_workspace_context(db, round_.id, round_.round_type),
            # "both"-modality rounds may have this reply spoken via TTS even if the
            # candidate typed it (the candidate can switch channels mid-round), so
            # they get the same brevity treatment as pure voice - only "text" rounds
            # keep the original, longer-form written style.
            voice_mode=round_.modality in ("voice", "both"),
            # Persist the same focus note across every turn of a drill round, not
            # just the opening one (round_.drill_focus_hint is None for every
            # normal round - see orchestrator.start_drill_round).
            focus_hint=round_.drill_focus_hint,
            probe_hint=probe_hint,
            **coding_kwargs,
        )
    except Exception as exc:
        logger.exception("Interviewer failed to produce a reply turn for round_id=%s", round_.id)
        raise InterviewerUnavailableError(
            "The interviewer's AI backend is temporarily unavailable (rate limited or having an "
            "outage) - please try again in a moment."
        ) from exc

    next_index = len(turns)
    candidate_turn = TranscriptTurn(
        round_id=round_.id,
        turn_index=next_index,
        speaker="candidate",
        text=text,
        phase=round_.phase,
    )
    interviewer_turn = TranscriptTurn(
        round_id=round_.id,
        turn_index=next_index + 1,
        speaker="interviewer",
        text=output.utterance,
        phase=output.phase.value,
        competency_tags=output.competency_tags,
    )
    db.add_all([candidate_turn, interviewer_turn])

    round_.phase = output.phase.value
    round_.coverage = {k: v.value for k, v in output.coverage.items()}
    if output.action.value == "WRAP" or state.time_remaining_sec <= 0:
        round_.status = "WRAP_UP"

    db.commit()
    db.refresh(interviewer_turn)
    # Evidence extraction + belief update + picker decision (specs/005) - inline
    # for the rule-based extractor, a background thread for the LLM one, so the
    # interviewer reply above never waits on it. Never raises.
    worldmodel_service.schedule_after_turn(db, round_.id)
    return interviewer_turn


def submit_round(db: DBSession, round_: RoundAttempt) -> RoundEvaluation:
    if round_.status not in ("SUBMITTED", "EVALUATING", "EVALUATED"):
        round_.status = "SUBMITTED"
        round_.submitted_at = _now()
        db.commit()

    existing = db.get(EvaluationRecord, round_.id)
    if existing is not None:
        return _record_to_evaluation(existing)

    round_.status = "EVALUATING"
    db.commit()

    # Make sure every answer is in the world model before the report is read
    # (specs/005). Never raises - a failure only means a thinner path map.
    worldmodel_service.catch_up(db, round_.id)

    turns = load_transcript(db, round_.id)
    transcript = [
        {"speaker": t.speaker, "text": t.text, "phase": t.phase, "competency_tags": t.competency_tags or []}
        for t in turns
    ]

    # RZ-02 (UI/UX review, 2026-09-29): a round submitted with zero candidate
    # responses (abandoned right after starting, or ended immediately) used
    # to go through the exact same rubric scoring as a genuinely completed
    # round - every dimension defaults to NOT_COVERED with nothing to
    # collect evidence from, so it always came out 0% readiness / NO HIRE,
    # indistinguishable from a real, thorough failure. Checked here, before
    # the evaluator (and any LLM synthesis call) even runs, rather than
    # inside RuleBasedEvaluator/LLMEvaluator - this is a round-level
    # question ("was there anything to score at all"), not something either
    # evaluator implementation should each have to reimplement, and it also
    # means an empty round never spends a real LLM call on nothing.
    not_assessed = not any(t["speaker"] == "candidate" and t["text"].strip() for t in transcript)

    if not_assessed:
        scored = ScoredRound(
            round_id=round_.id, dimension_scores=[], readiness_pct=0, hire_signal="NOT_ASSESSED", not_assessed=True
        )
        strengths, weaknesses = [], []
        concern = "Not assessed - no responses were submitted before this round ended."
        plan = []
        level_calibration = LevelCalibration(
            narrative=(
                "Not assessed - no responses were submitted before this round ended, "
                "so there's nothing to calibrate a level against."
            )
        )
    else:
        try:
            scored = get_evaluator().evaluate(
                round_id=round_.id,
                round_type=round_.round_type,
                transcript=transcript,
                final_coverage=round_.coverage,
            )
            strengths, weaknesses = strengths_and_weaknesses(scored.dimension_scores)

            if os.environ.get("OPENAI_API_KEY"):
                concern, plan = llm_report_synthesis(
                    OpenAIGateway(), scored.dimension_scores, round_type=round_.round_type
                )
            else:
                concern = primary_concern(scored.dimension_scores)
                plan = build_improvement_plan(scored.dimension_scores)
        except Exception as exc:
            logger.exception("Evaluation failed for round_id=%s", round_.id)
            # Back out of EVALUATING (committed above) so a retried Submit re-enters
            # this function cleanly instead of finding the round permanently wedged.
            round_.status = "SUBMITTED"
            db.commit()
            raise EvaluationUnavailableError(
                "Scoring this round hit a temporary error (rate limited or an outage) - "
                "please try Submit again in a moment."
            ) from exc
        level_calibration = calibrate_level(scored.readiness_pct, scored.hire_signal)

    evaluation = RoundEvaluation(
        round_id=round_.id,
        dimension_scores=scored.dimension_scores,
        readiness_pct=scored.readiness_pct,
        hire_signal=scored.hire_signal,
        primary_concern=concern,
        strengths=strengths,
        weaknesses=weaknesses,
        improvement_plan=plan,
        level_calibration=level_calibration,
        not_assessed=scored.not_assessed,
    )

    record = EvaluationRecord(
        round_id=round_.id,
        dimension_scores=[d.model_dump() for d in evaluation.dimension_scores],
        readiness_pct=evaluation.readiness_pct,
        hire_signal=evaluation.hire_signal,
        primary_concern=evaluation.primary_concern,
        strengths=evaluation.strengths,
        weaknesses=evaluation.weaknesses,
        improvement_plan=[i.model_dump() for i in evaluation.improvement_plan],
        not_assessed=evaluation.not_assessed,
    )
    db.add(record)
    round_.status = "EVALUATED"
    db.commit()
    return evaluation


def _record_to_evaluation(record: EvaluationRecord) -> RoundEvaluation:
    # RZ-02: a stored not_assessed record still carries placeholder
    # readiness_pct=0/hire_signal="NOT_ASSESSED" (see EvaluationRecord's
    # docstring) - calibrate_level would turn that into a misleading "this
    # round doesn't clear the bar" narrative every time it's re-read, so
    # skip it the same way submit_round does when the record is fresh.
    level_calibration = (
        LevelCalibration(
            narrative=(
                "Not assessed - no responses were submitted before this round ended, "
                "so there's nothing to calibrate a level against."
            )
        )
        if record.not_assessed
        else calibrate_level(record.readiness_pct, record.hire_signal)
    )
    return RoundEvaluation(
        round_id=record.round_id,
        dimension_scores=record.dimension_scores,
        readiness_pct=record.readiness_pct,
        hire_signal=record.hire_signal,
        primary_concern=record.primary_concern,
        strengths=record.strengths,
        weaknesses=record.weaknesses,
        improvement_plan=record.improvement_plan,
        level_calibration=level_calibration,
        not_assessed=record.not_assessed,
    )


def get_report(db: DBSession, round_id: str) -> RoundEvaluation | None:
    record = db.get(EvaluationRecord, round_id)
    if record is None:
        return None
    return _record_to_evaluation(record)


def history_item_out(round_: RoundAttempt, evaluation: RoundEvaluation | None) -> HistoryItemOut:
    """Shared by list_rounds and compare_rounds below so both render the exact
    same summary shape for a round - readiness_pct/hire_signal come from the
    evaluation when one exists (None for a round that hasn't been submitted/
    evaluated yet), everything else from the round itself."""
    # RZ-02: a not_assessed evaluation exists (the round did reach
    # EVALUATED) but has nothing real to report - treated the same as "no
    # evaluation yet" here so every place that already does
    # `readiness_pct is not None` to mean "has a real score" (progress
    # trends, report summary averages, etc.) excludes it automatically.
    has_real_score = evaluation is not None and not evaluation.not_assessed
    return HistoryItemOut(
        id=round_.id,
        loop_attempt_id=round_.loop_attempt_id,
        round_type=round_.round_type,
        role_family=round_.role_family,
        level=round_.level,
        domain=round_.domain,
        company_profile=round_.company_profile,
        duration_minutes=round_.duration_minutes,
        status=round_.status,
        readiness_pct=evaluation.readiness_pct if has_real_score else None,
        hire_signal=evaluation.hire_signal if has_real_score else None,
        created_at=round_.created_at,
        submitted_at=round_.submitted_at,
    )


def compare_rounds(db: DBSession, round_a: RoundAttempt, round_b: RoundAttempt) -> RoundComparisonOut | None:
    """tasks.md P1 item 16 - "a lightweight version of Longitudinal Progress...
    two-attempt comparison, not full trend tracking yet." Pure arithmetic over
    two already-persisted EvaluationRecord rows (via get_report - no new LLM
    call), so this works even while the interviewer/evaluator providers are
    down. Always orders older -> newer by created_at regardless of which
    order round_a/round_b were passed in, so every delta field reads as
    "improvement over time" rather than depending on argument order. Returns
    None if either round hasn't been evaluated yet - apps/api/routes/rounds.py
    turns that into a 409, same pattern as EvaluationUnavailableError above."""
    older, newer = (round_a, round_b) if round_a.created_at <= round_b.created_at else (round_b, round_a)
    eval_older = get_report(db, older.id)
    eval_newer = get_report(db, newer.id)
    # RZ-02: a not_assessed round (empty - nothing to compare) is treated
    # the same as "not evaluated yet" here, same reasoning as
    # history_item_out above.
    if eval_older is None or eval_newer is None or eval_older.not_assessed or eval_newer.not_assessed:
        return None

    newer_by_dim = {d.dimension: d for d in eval_newer.dimension_scores}
    dimension_deltas = [
        DimensionScoreDelta(
            dimension=d.dimension,
            label=d.label,
            score_older=d.score,
            score_newer=newer_by_dim[d.dimension].score,
            delta=newer_by_dim[d.dimension].score - d.score,
        )
        for d in eval_older.dimension_scores
        if d.dimension in newer_by_dim
    ]

    return RoundComparisonOut(
        round_older=history_item_out(older, eval_older),
        round_newer=history_item_out(newer, eval_newer),
        evaluation_older=eval_older,
        evaluation_newer=eval_newer,
        readiness_delta=eval_newer.readiness_pct - eval_older.readiness_pct,
        hire_signal_older=eval_older.hire_signal,
        hire_signal_newer=eval_newer.hire_signal,
        dimension_deltas=dimension_deltas,
    )


def loop_committee_eligible(db: DBSession, loop: LoopAttempt) -> list[tuple[str, RoundAttempt, RoundEvaluation]]:
    """A loop's evaluated real rounds (round_type, RoundAttempt, RoundEvaluation),
    sorted by PlannedRound.sort_order, if the loop qualifies for a committee
    synthesis - else []. Ports LoopList.tsx::classifyLoop's "finished" logic
    server-side (every real-round-type entry in the loop has reached EVALUATED)
    plus specs/002 P0.6's own "nothing to synthesize below 2 rounds" cut - a
    loop with 0 or 1 real rounds started/evaluated is never eligible, and
    neither is one where a real round is still in progress. Round types with no
    interviewer yet (REAL_ROUND_TYPES) never block or count toward this, same
    as classifyLoop's own "disabled round types don't block finished" rule."""
    planned = list_planned_rounds(db, loop.id)
    real_planned = [p for p in planned if p.round_type in REAL_ROUND_TYPES]
    if not real_planned:
        return []
    if not all(p.round_attempt_id is not None for p in real_planned):
        return []

    result: list[tuple[str, RoundAttempt, RoundEvaluation]] = []
    for p in real_planned:
        round_ = db.get(RoundAttempt, p.round_attempt_id)
        if round_ is None or round_.status != "EVALUATED":
            return []
        evaluation = get_report(db, round_.id)
        # RZ-02: a not_assessed round (nothing was actually submitted) has
        # no real signal to synthesize into a committee verdict - treat the
        # loop as not yet eligible, same as if this round were still in
        # progress, rather than let it drag the synthesis toward a
        # fabricated 0%/NO HIRE contribution.
        if evaluation is None or evaluation.not_assessed:
            return []
        result.append((p.round_type, round_, evaluation))

    if len(result) < 2:
        return []
    return result


def _committee_target_level(rounds: list[tuple[str, RoundAttempt, RoundEvaluation]]) -> str:
    """Same "{Level} {Role}" label _derive_auto_name builds for loop names,
    reused here so the committee's level_signal talks about the same target
    the candidate saw when they built the loop."""
    _, first_round, _ = rounds[0]
    label = " ".join(_title_word(w) for w in f"{first_round.level}_{first_round.role_family}".split("_"))
    return label


def _record_to_committee_report(record: LoopCommitteeRecord) -> CommitteeReport:
    return CommitteeReport(
        overall_readiness_pct=record.overall_readiness_pct,
        overall_hire_signal=record.overall_hire_signal,
        confidence=record.confidence,
        headline=record.headline,
        strengths=record.strengths,
        concerns=record.concerns,
        level_signal=record.level_signal,
        key_evidence=record.key_evidence,
    )


def get_committee_report(db: DBSession, loop: LoopAttempt) -> tuple[CommitteeReport, list[str], datetime] | None:
    """Read-only (specs/002 P0.6) - GET /v1/loops/{id}/committee. Returns the
    cached LoopCommitteeRecord, its rounds_included, and updated_at only if it
    is still fresh (built from exactly the loop's currently-eligible round set);
    None if the loop isn't eligible yet, nothing has been generated yet, or a
    newly-evaluated round has made the cached one stale - either way the
    frontend's next move is the same (fall back to POST), so this doesn't
    distinguish those cases to the caller."""
    eligible = loop_committee_eligible(db, loop)
    if not eligible:
        return None
    current_ids = sorted(round_.id for _, round_, _ in eligible)

    record = db.get(LoopCommitteeRecord, loop.id)
    if record is None or sorted(record.rounds_included) != current_ids:
        return None
    return _record_to_committee_report(record), record.rounds_included, record.updated_at


def generate_committee_report(db: DBSession, loop: LoopAttempt) -> tuple[CommitteeReport, list[str], datetime]:
    """Builds-or-returns-cached-fresh (specs/002 P0.6) - POST
    /v1/loops/{id}/committee. Raises CommitteeNotReadyError if the loop doesn't
    qualify (apps/api/routes/loops.py turns that into a 400). Only calls the
    LLM (or the rule-based fallback with no OPENAI_API_KEY, same
    os.environ.get("OPENAI_API_KEY") branch submit_round uses) when the cached
    LoopCommitteeRecord is missing or stale - a loop whose round set hasn't
    changed since it was last synthesized never pays for a second LLM call
    just because the page was viewed again."""
    eligible = loop_committee_eligible(db, loop)
    if not eligible:
        raise CommitteeNotReadyError(
            "This loop needs at least 2 completed interviews before a committee verdict is available."
        )
    current_ids = sorted(round_.id for _, round_, _ in eligible)

    record = db.get(LoopCommitteeRecord, loop.id)
    if record is not None and sorted(record.rounds_included) == current_ids:
        return _record_to_committee_report(record), record.rounds_included, record.updated_at

    target_level = _committee_target_level(eligible)
    rounds_for_synthesis = [(round_type, evaluation) for round_type, _, evaluation in eligible]

    try:
        if os.environ.get("OPENAI_API_KEY"):
            report = llm_committee_synthesis(OpenAIGateway(), rounds_for_synthesis, target_level)
        else:
            report = rule_based_committee_synthesis(rounds_for_synthesis, target_level)
    except Exception as exc:
        logger.exception("Committee synthesis failed for loop_id=%s", loop.id)
        raise CommitteeUnavailableError(
            "Building the committee verdict hit a temporary error (rate limited or an outage) - "
            "please try again in a moment."
        ) from exc

    if record is None:
        record = LoopCommitteeRecord(loop_attempt_id=loop.id)
        db.add(record)
    record.rounds_included = current_ids
    record.overall_readiness_pct = report.overall_readiness_pct
    record.overall_hire_signal = report.overall_hire_signal
    record.confidence = report.confidence
    record.headline = report.headline
    record.strengths = report.strengths
    record.concerns = report.concerns
    record.level_signal = report.level_signal
    record.key_evidence = report.key_evidence
    db.commit()
    db.refresh(record)
    return report, record.rounds_included, record.updated_at


# --- Real Interview Experience + Outcome (specs/002-full-loop-platform P0.11/P0.12) ---


def _rounds_to_json(rounds: list) -> list[dict]:
    return [r.model_dump() for r in rounds]


def create_real_interview_experience(
    db: DBSession, user_id: str, req: RealInterviewExperienceIn
) -> RealInterviewExperience:
    """POST /v1/real-interviews. `req.rounds` is whatever the frontend already
    has in hand - either typed by the candidate directly, or an AI-structured
    draft (structure_real_interview_text below) they reviewed and edited -
    never re-derived here. If linked_loop_attempt_id is given, it must
    actually belong to this user (same ownership discipline
    apps/api/routes/loops.py::_get_owned_loop already enforces for every
    other loop-scoped operation) - raises LinkedLoopNotFoundError otherwise,
    rather than silently dropping or silently trusting an unowned id."""
    if req.linked_loop_attempt_id is not None:
        loop = db.get(LoopAttempt, req.linked_loop_attempt_id)
        if loop is None or loop.user_id != user_id:
            raise LinkedLoopNotFoundError("The loop you tried to link this interview to could not be found.")

    experience = RealInterviewExperience(
        user_id=user_id,
        company=req.company,
        role_family=req.role_family,
        level=req.level,
        domain=req.domain,
        interview_date=req.interview_date,
        linked_loop_attempt_id=req.linked_loop_attempt_id,
        rounds=_rounds_to_json(req.rounds),
        notes=req.notes,
        self_assessment=req.self_assessment,
        visibility=req.visibility,
    )
    db.add(experience)
    db.commit()
    db.refresh(experience)
    return experience


def list_real_interview_experiences(db: DBSession, user_id: str) -> list[RealInterviewExperience]:
    return (
        db.query(RealInterviewExperience)
        .filter(RealInterviewExperience.user_id == user_id)
        .order_by(RealInterviewExperience.interview_date.desc())
        .all()
    )


def get_owned_real_interview_experience(
    db: DBSession, user_id: str, experience_id: str
) -> RealInterviewExperience | None:
    """Shared existence+ownership check - mirrors apps/api/routes/loops.py's
    _get_owned_loop, but lives here rather than in the route module since
    every mutating operation below (update/delete/outcome) needs the exact
    same check before it can safely act on a row."""
    experience = db.get(RealInterviewExperience, experience_id)
    if experience is None or experience.user_id != user_id:
        return None
    return experience


def update_real_interview_experience(
    db: DBSession, experience: RealInterviewExperience, req: RealInterviewExperienceIn
) -> RealInterviewExperience:
    """Caller must already have resolved and owner-checked `experience` (see
    get_owned_real_interview_experience) - same split as delete_loop/
    generate_committee_report, which take an already-owned LoopAttempt rather
    than re-deriving ownership themselves."""
    if req.linked_loop_attempt_id != experience.linked_loop_attempt_id and req.linked_loop_attempt_id is not None:
        loop = db.get(LoopAttempt, req.linked_loop_attempt_id)
        if loop is None or loop.user_id != experience.user_id:
            raise LinkedLoopNotFoundError("The loop you tried to link this interview to could not be found.")

    experience.company = req.company
    experience.role_family = req.role_family
    experience.level = req.level
    experience.domain = req.domain
    experience.interview_date = req.interview_date
    experience.linked_loop_attempt_id = req.linked_loop_attempt_id
    experience.rounds = _rounds_to_json(req.rounds)
    experience.notes = req.notes
    experience.self_assessment = req.self_assessment
    experience.visibility = req.visibility
    db.commit()
    db.refresh(experience)
    return experience


def delete_real_interview_experience(db: DBSession, experience: RealInterviewExperience) -> None:
    """Also deletes its RealInterviewOutcome row if one exists - same orphan-
    cleanup discipline delete_loop's own LoopCommitteeRecord cleanup already
    established (no SQLite FK cascade in this app, so this has to be
    explicit, not assumed)."""
    db.query(RealInterviewOutcome).filter(RealInterviewOutcome.experience_id == experience.id).delete()
    db.delete(experience)
    db.commit()


def upsert_real_interview_outcome(
    db: DBSession, experience: RealInterviewExperience, req: RealInterviewOutcomeIn
) -> RealInterviewOutcome:
    """POST /v1/real-interviews/{id}/outcome - create the one outcome row for
    this experience, or update it in place if the candidate is reporting a
    change (e.g. "waiting" -> "offer" weeks later). Never a second row -
    same "current state, upserted" shape as generate_committee_report's
    LoopCommitteeRecord handling."""
    outcome = db.get(RealInterviewOutcome, experience.id)
    if outcome is None:
        outcome = RealInterviewOutcome(experience_id=experience.id)
        db.add(outcome)
    outcome.status = req.status
    outcome.stage = req.stage
    outcome.target_level = req.target_level
    outcome.offered_level = req.offered_level
    outcome.notes = req.notes
    db.commit()
    db.refresh(outcome)
    return outcome


def real_interview_prediction(db: DBSession, experience: RealInterviewExperience) -> PredictionSnapshotOut | None:
    """Live-computed, never stored redundantly - specs/002 P0.12's "store
    simulation prediction vs. real-world outcome", read fresh every time
    rather than snapshotted at link time, so it can never drift from
    whatever the linked loop's real evaluation currently says. Returns None
    when there's genuinely nothing to show (no link, linked loop deleted, or
    nothing in it evaluated yet) - never a fabricated placeholder.

    Tries the loop's Virtual Hiring Committee verdict first (the strongest
    available signal once a loop has one - specs/002 P0.6); if the loop never
    reached committee eligibility (fewer than 2 evaluated real rounds), falls
    back to that loop's single best evaluated round instead of showing
    nothing just because the loop was smaller."""
    if experience.linked_loop_attempt_id is None:
        return None
    loop = db.get(LoopAttempt, experience.linked_loop_attempt_id)
    if loop is None:
        return None

    committee = get_committee_report(db, loop)
    if committee is not None:
        report, _rounds_included, _updated_at = committee
        return PredictionSnapshotOut(
            source="committee",
            readiness_pct=report.overall_readiness_pct,
            hire_signal=report.overall_hire_signal,
        )

    best: RoundEvaluation | None = None
    for planned in list_planned_rounds(db, loop.id):
        if planned.round_attempt_id is None:
            continue
        evaluation = get_report(db, planned.round_attempt_id)
        # RZ-02: skip not_assessed rounds entirely rather than let their
        # placeholder readiness_pct=0 ever be picked as "best".
        if evaluation is not None and not evaluation.not_assessed and (best is None or evaluation.readiness_pct > best.readiness_pct):
            best = evaluation
    if best is None:
        return None
    return PredictionSnapshotOut(source="round", readiness_pct=best.readiness_pct, hire_signal=best.hire_signal)


def structure_real_interview_text(raw_text: str, hints: str = "") -> StructuredExperience:
    """POST /v1/real-interviews/structure - preview only, nothing persisted
    (see roundzero.debrief.real_interview's module docstring for why). Same
    os.environ.get("OPENAI_API_KEY") branch every other LLM feature in this
    codebase uses (submit_round, generate_committee_report)."""
    if os.environ.get("OPENAI_API_KEY"):
        return llm_structure_experience(OpenAIGateway(), raw_text, hints)
    return rule_based_structure_experience(raw_text)


# --- Prep Plans (user-pitched feature: candidate-curated practice questions,
# not from the P0 backlog - see apps/api/models.py's PrepPlan/PrepPlanArea/
# PrepPlanQuestion docstrings for the full design, and prep_plan.suggest's
# module docstring for the AI-suggest half) ---


def _plan_target_role(plan: PrepPlan) -> TargetRole:
    return TargetRole(
        role_family=plan.role_family,
        level=plan.level,
        domain=plan.domain,
        company_profile=plan.company_profile,
    )


def create_prep_plan(db: DBSession, user_id: str, req: PrepPlanIn) -> PrepPlan:
    plan = PrepPlan(
        user_id=user_id,
        name=req.name,
        role_family=req.role_family,
        level=req.level,
        domain=req.domain,
        company_profile=req.company_profile,
        duration_minutes=req.duration_minutes,
        mode=req.mode,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def list_prep_plans(db: DBSession, user_id: str) -> list[PrepPlan]:
    return db.query(PrepPlan).filter(PrepPlan.user_id == user_id).order_by(PrepPlan.created_at.desc()).all()


def get_owned_prep_plan(db: DBSession, user_id: str, plan_id: str) -> PrepPlan | None:
    plan = db.get(PrepPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        return None
    return plan


def update_prep_plan(db: DBSession, plan: PrepPlan, req: PrepPlanIn) -> PrepPlan:
    """Caller must already have resolved and owner-checked `plan` (see
    get_owned_prep_plan) - same split as update_real_interview_experience."""
    plan.name = req.name
    plan.role_family = req.role_family
    plan.level = req.level
    plan.domain = req.domain
    plan.company_profile = req.company_profile
    plan.duration_minutes = req.duration_minutes
    plan.mode = req.mode
    db.commit()
    db.refresh(plan)
    return plan


def delete_prep_plan(db: DBSession, plan: PrepPlan) -> None:
    """Cascades areas -> questions explicitly (no SQLite FK cascade in this
    app - same discipline delete_real_interview_experience/delete_loop
    already established). Any RoundAttempt.prep_plan_question_id pointing at
    a deleted question is left as-is - it's a display-only reference used
    only to compute that question's own progress badge, and once the
    question is gone nothing reads it again."""
    area_ids = [row[0] for row in db.query(PrepPlanArea.id).filter(PrepPlanArea.plan_id == plan.id).all()]
    if area_ids:
        db.query(PrepPlanQuestion).filter(PrepPlanQuestion.area_id.in_(area_ids)).delete(synchronize_session="fetch")
        db.query(PrepPlanArea).filter(PrepPlanArea.plan_id == plan.id).delete(synchronize_session="fetch")
    db.delete(plan)
    db.commit()


def get_owned_prep_plan_area(db: DBSession, user_id: str, area_id: str) -> PrepPlanArea | None:
    area = db.get(PrepPlanArea, area_id)
    if area is None:
        return None
    plan = db.get(PrepPlan, area.plan_id)
    if plan is None or plan.user_id != user_id:
        return None
    return area


def add_prep_plan_area(db: DBSession, plan: PrepPlan, req: PrepPlanAreaIn) -> PrepPlanArea:
    if req.round_type not in REAL_ROUND_TYPES:
        available = ", ".join(sorted(REAL_ROUND_TYPES))
        raise RoundTypeNotAvailableError(
            f"'{req.round_type}' doesn't have a real interviewer yet - only {available} "
            "can be added to a plan today."
        )
    sort_order = db.query(PrepPlanArea).filter(PrepPlanArea.plan_id == plan.id).count()
    area = PrepPlanArea(plan_id=plan.id, round_type=req.round_type, label=req.label, sort_order=sort_order)
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


def delete_prep_plan_area(db: DBSession, area: PrepPlanArea) -> None:
    db.query(PrepPlanQuestion).filter(PrepPlanQuestion.area_id == area.id).delete(synchronize_session="fetch")
    db.delete(area)
    db.commit()


def get_owned_prep_plan_question(db: DBSession, user_id: str, question_id: str) -> PrepPlanQuestion | None:
    question = db.get(PrepPlanQuestion, question_id)
    if question is None:
        return None
    area = db.get(PrepPlanArea, question.area_id)
    if area is None:
        return None
    plan = db.get(PrepPlan, area.plan_id)
    if plan is None or plan.user_id != user_id:
        return None
    return question


def list_bank_scenarios_for_area(db: DBSession, area: PrepPlanArea) -> list[dict]:
    """GET /v1/prep-plans/areas/{id}/bank-scenarios - the "add from bank"
    browse list, filtered to the plan's level/domain (filter_bank_scenarios'
    same progressive-relax behavior pick_scenario uses), excluding scenarios
    already added to this area so the same one can't be added twice."""
    plan = db.get(PrepPlan, area.plan_id)
    existing_ids = frozenset(
        q.scenario_id for q in db.query(PrepPlanQuestion).filter(PrepPlanQuestion.area_id == area.id).all() if q.scenario_id
    )
    return filter_bank_scenarios(area.round_type, _plan_target_role(plan), existing_ids)


def _next_question_sort_order(db: DBSession, area_id: str) -> int:
    return db.query(PrepPlanQuestion).filter(PrepPlanQuestion.area_id == area_id).count()


def add_prep_plan_question_from_bank(db: DBSession, area: PrepPlanArea, scenario_id: str) -> PrepPlanQuestion:
    scenarios = load_scenarios(area.round_type)
    match = next((s for s in scenarios if scenario_id_of(s) == scenario_id), None)
    if match is None:
        raise BankScenarioNotFoundError(f"'{scenario_id}' isn't a known {area.round_type} scenario.")
    question = PrepPlanQuestion(
        area_id=area.id,
        prompt=match["prompt"],
        notes=None,
        source="bank",
        scenario_id=scenario_id,
        sort_order=_next_question_sort_order(db, area.id),
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def add_custom_prep_plan_question(db: DBSession, area: PrepPlanArea, req: AddCustomQuestionIn) -> PrepPlanQuestion:
    if area.round_type not in FREEFORM_ROUND_TYPES:
        raise CustomQuestionNotAllowedError(
            f"'{area.round_type}' questions need to come from the scenario bank - a freeform "
            "question here couldn't actually run (no starter code/tests to work from)."
        )
    question = PrepPlanQuestion(
        area_id=area.id,
        prompt=req.prompt,
        notes=req.notes,
        source="custom",
        scenario_id=None,
        sort_order=_next_question_sort_order(db, area.id),
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def add_suggested_prep_plan_question(
    db: DBSession, area: PrepPlanArea, suggestion: SuggestedQuestion
) -> PrepPlanQuestion:
    """Adds one specific result previously returned by
    suggest_prep_plan_questions - called only when the candidate clicks
    "Add" on that suggestion, never automatically (see prep_plan.suggest's
    module docstring). A suggestion carrying a scenario_id (the Coding/
    no-key bank fallback) is added exactly like
    add_prep_plan_question_from_bank, source="bank" - it's a real bank
    scenario, just surfaced via the suggest flow instead of the browse flow.
    A freeform suggestion (scenario_id is None) is added with source="ai" so
    the UI can show where it came from; behaves identically to a "custom"
    question everywhere else."""
    if suggestion.scenario_id is not None:
        return add_prep_plan_question_from_bank(db, area, suggestion.scenario_id)
    question = PrepPlanQuestion(
        area_id=area.id,
        prompt=suggestion.prompt,
        notes=suggestion.notes or None,
        source="ai",
        scenario_id=None,
        sort_order=_next_question_sort_order(db, area.id),
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def delete_prep_plan_question(db: DBSession, question: PrepPlanQuestion) -> None:
    db.delete(question)
    db.commit()


def suggest_prep_plan_questions(db: DBSession, area: PrepPlanArea) -> list[SuggestedQuestion]:
    """POST /v1/prep-plans/areas/{id}/suggest-questions - preview only,
    nothing persisted (see prep_plan.suggest's module docstring). Coding
    areas (and any other round_type outside FREEFORM_ROUND_TYPES) always get
    the bank fallback, regardless of OPENAI_API_KEY - a freeform LLM
    suggestion is never even attempted for them, same restriction
    add_custom_prep_plan_question enforces for direct authoring."""
    plan = db.get(PrepPlan, area.plan_id)
    target_role = _plan_target_role(plan)
    existing_questions = db.query(PrepPlanQuestion).filter(PrepPlanQuestion.area_id == area.id).all()
    existing_scenario_ids = frozenset(q.scenario_id for q in existing_questions if q.scenario_id)

    if area.round_type not in FREEFORM_ROUND_TYPES:
        return suggest_questions_from_bank(area.round_type, target_role, existing_scenario_ids)

    if os.environ.get("OPENAI_API_KEY"):
        existing_prompts = [q.prompt for q in existing_questions]
        return llm_suggest_questions(OpenAIGateway(), area.round_type, target_role, existing_prompts)
    return suggest_questions_from_bank(area.round_type, target_role, existing_scenario_ids)


def start_round_from_plan_question(
    db: DBSession, user_id: str, question_id: str
) -> tuple[RoundAttempt, TranscriptTurn]:
    """The "click a question, go" entry point (user-pitched Prep Plans
    feature) - resolves plan -> area -> question ownership itself and raises
    PlanQuestionNotFoundError on failure (see that exception's docstring for
    why this one function departs from the get_owned_* -> None split every
    other Prep Plan mutation uses), builds the exact scenario dict that
    question represents, and hands it to _start_round via scenario_override
    so starting from a plan question goes through the exact same
    round-creation path as every other way to start a round - no parallel
    code path, no interviewer changes.

    A question with source="bank" gets looked up FRESH from the YAML bank by
    scenario_id (title/constraints/entry_point/starter_code/test_cases
    included when present, same as any other bank-sourced round) rather than
    trusting the question's own `prompt` column, which is a display-only
    snapshot - this guarantees the started round is never missing the
    structured fields Coding's workspace needs. A custom/ai question becomes
    a minimal {"id": ..., "prompt": ...} dict, which is fine since those are
    only ever offered for prompt-only round types (FREEFORM_ROUND_TYPES).

    Runs against the PLAN's own stored role/level/domain/company/duration/
    mode - never re-asked, so picking a question really is one click - and
    starts its own fresh loop, same "creates its own fresh one-round loop"
    shape create_round already uses for the original /setup quick-start
    path (just prefixed "Plan-" instead of "Practice-" in the auto-name, so
    the two are distinguishable in My Loops)."""
    question = get_owned_prep_plan_question(db, user_id, question_id)
    if question is None:
        raise PlanQuestionNotFoundError(f"Prep plan question {question_id} not found")
    area = db.get(PrepPlanArea, question.area_id)
    plan = db.get(PrepPlan, area.plan_id)

    if question.source == "bank":
        scenarios = load_scenarios(area.round_type)
        match = next((s for s in scenarios if scenario_id_of(s) == question.scenario_id), None)
        scenario = match if match is not None else {"id": question.scenario_id or question.id, "prompt": question.prompt}
    else:
        scenario = {"id": f"plan_question_{question.id}", "prompt": question.prompt}

    loop_attempt = LoopAttempt(
        user_id=user_id,
        name=_derive_auto_name(db, user_id, plan.role_family, plan.level, plan.company_profile, prefix="Plan"),
    )
    db.add(loop_attempt)
    db.flush()

    round_, turn = _start_round(
        db,
        user_id,
        loop_attempt.id,
        round_type=area.round_type,
        role_family=plan.role_family,
        level=plan.level,
        domain=plan.domain,
        company_profile=plan.company_profile,
        duration_minutes=plan.duration_minutes,
        mode=plan.mode,
        scenario_override=scenario,
        prep_plan_question_id=question.id,
    )

    # create_round's docstring: "every RoundAttempt has exactly one
    # PlannedRound, no special-casing needed elsewhere" - this entrypoint
    # creates its own fresh loop exactly like create_round does, so it must
    # keep that same invariant. Missing this made the dashboard's Upcoming
    # section show a "Plan-Generic ... - 0 of 0 interviews started" loop for
    # every round started from a plan question (caught live 2026-09-03 - the
    # round itself worked fine, but nothing ever counted it as planned).
    planned = PlannedRound(
        loop_attempt_id=loop_attempt.id,
        user_id=user_id,
        round_type=area.round_type,
        role_family=plan.role_family,
        level=plan.level,
        domain=plan.domain,
        company_profile=plan.company_profile,
        duration_minutes=plan.duration_minutes,
        modality=plan.mode,
        sort_order=0,
        round_attempt_id=round_.id,
    )
    db.add(planned)
    db.commit()

    return round_, turn


def start_drill_round(
    db: DBSession, user_id: str, source_round: RoundAttempt, priority: int
) -> tuple[RoundAttempt, TranscriptTurn]:
    """"Practice this weakness" (user-requested Drills feature) - the report
    page (apps/web/app/reports/[roundId]/page.tsx) renders each
    RoundEvaluation.improvement_plan item next to a "Practice this" button;
    clicking it calls this function with that item's own `priority` (1 =
    highest priority, per ImprovementItem's docstring) to find the exact
    item again server-side rather than trusting a resubmitted dimension/
    recommendation string from the client.

    Closes the Assess -> Diagnose -> Practice -> Reassess loop specs/002
    P0.10 describes but never built: build_improvement_plan (Diagnose)
    already ran at submit time and is sitting in EvaluationRecord unused by
    anything - this is the first thing that lets a candidate act on it.

    Deliberately does NOT fabricate a scenario for the drilled dimension -
    picks a normal scenario via the standard _start_round path (same
    round_type/role_family/level/domain/company/duration/modality as the
    source round) and instead biases the *interviewer's questioning* toward
    the weak dimension via drill_focus_hint -> focus_hint (see
    interviewers/*/agent.py's next_turn). A hand-authored scenario would hit
    the exact wall start_round_from_plan_question already worked around for
    Coding (_SCENARIO_META_KEYS - starter_code/test_cases/entry_point a
    freeform prompt has no way to supply) - reusing the real bank keeps this
    safe for every round_type including Coding, at the cost of the drill
    round not being hand-picked-for-this-weakness content, only
    hand-picked-for-this-weakness *questioning*.

    Starts its own fresh one-round loop, same shape create_round/
    start_round_from_plan_question already use, prefixed "Drill-" so it's
    distinguishable in My Loops - and writes the matching PlannedRound
    (create_round's docstring: "every RoundAttempt has exactly one
    PlannedRound") the same way both of those already do."""
    record = db.get(EvaluationRecord, source_round.id)
    if record is None:
        raise DrillSourceNotFoundError(f"Round {source_round.id} has not been evaluated yet")

    item = next((i for i in record.improvement_plan if i.get("priority") == priority), None)
    if item is None:
        raise DrillSourceNotFoundError(
            f"No improvement plan item with priority {priority} for round {source_round.id}"
        )

    focus_hint = f"{item['dimension']}: {item['recommendation']}"

    loop_attempt = LoopAttempt(
        user_id=user_id,
        name=_derive_auto_name(
            db, user_id, source_round.role_family, source_round.level, source_round.company_profile, prefix="Drill"
        ),
    )
    db.add(loop_attempt)
    db.flush()

    round_, turn = _start_round(
        db,
        user_id,
        loop_attempt.id,
        round_type=source_round.round_type,
        role_family=source_round.role_family,
        level=source_round.level,
        domain=source_round.domain,
        company_profile=source_round.company_profile,
        duration_minutes=source_round.duration_minutes,
        mode=source_round.modality,
        drill_focus_hint=focus_hint,
    )

    planned = PlannedRound(
        loop_attempt_id=loop_attempt.id,
        user_id=user_id,
        round_type=source_round.round_type,
        role_family=source_round.role_family,
        level=source_round.level,
        domain=source_round.domain,
        company_profile=source_round.company_profile,
        duration_minutes=source_round.duration_minutes,
        modality=source_round.modality,
        sort_order=0,
        round_attempt_id=round_.id,
    )
    db.add(planned)
    db.commit()

    return round_, turn


def question_progress(db: DBSession, question_id: str) -> QuestionProgressOut:
    """Live-computed, never stored - same "compute at read time" discipline
    real_interview_prediction already established. Looks at every
    RoundAttempt stamped with this question's id
    (start_round_from_plan_question sets that), most recent first, so the
    plan page's progress badge always reflects reality even if a question's
    text or source was edited after an attempt."""
    attempts = (
        db.query(RoundAttempt)
        .filter(RoundAttempt.prep_plan_question_id == question_id)
        .order_by(RoundAttempt.created_at.desc())
        .all()
    )
    if not attempts:
        return QuestionProgressOut(attempts=0)

    latest = attempts[0]
    evaluation = get_report(db, latest.id)
    # RZ-02: same has_real_score treatment as history_item_out above - a
    # not_assessed evaluation reads as "no score yet", not a fabricated 0%.
    has_real_score = evaluation is not None and not evaluation.not_assessed
    return QuestionProgressOut(
        attempts=len(attempts),
        latest_status=latest.status,
        latest_readiness_pct=evaluation.readiness_pct if has_real_score else None,
        latest_hire_signal=evaluation.hire_signal if has_real_score else None,
    )
