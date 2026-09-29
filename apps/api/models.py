"""
DB tables for auth (Milestone 1) plus the round runtime (Milestones 1-3):
LoopAttempt -> RoundAttempt -> TranscriptTurn, and EvaluationRecord.

Deliberate simplification vs. the full PRD section 19 data model
(CandidateProfile/TargetRole as their own tables, SessionEvent as a fully general
append-only event log): TargetRole fields live directly on RoundAttempt, and
TranscriptTurn is the only "event" type persisted, since Milestone 1-3 only ever
appends turns. Both are additive - promoting TargetRole to its own table or
widening TranscriptTurn into a general SessionEvent log if a second event type
shows up is a migration, not a rewrite (SQLite/DATABASE_URL, apps/api/db.py).

milestone-1.md's build checklist says "PostgreSQL schema" - superseded by the
already-resolved SQLite-for-V0 decision (apps/api/db.py's docstring); fixed in
that doc alongside this change.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from apps.api.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Local shadow profile of a Supabase auth.users row (apps/api/deps.py upserts
    this on first request). Keyed by `id` == Supabase's `sub` claim, which is the
    only identity Supabase guarantees is stable - `email` is NOT unique here even
    though it usually is in practice, because Supabase can mint more than one
    distinct auth.users.id for what a person considers "the same" email (e.g.
    signing in via Google after an earlier email/password or a since-deleted test
    account). Deduping on email in this table would crash real logins over an
    identity question that is Supabase's to resolve, not ours."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)
    # Set the first time this user completes a real Stripe Checkout (Phase 2 -
    # apps/api/routes/billing.py) from the session's `customer` field. Null
    # for anyone who hasn't paid yet, and not required to create a Checkout
    # Session in the first place (Stripe creates a Customer implicitly) -
    # this is purely for Phase 3's future Customer Portal / repeat-purchase
    # convenience (reusing the same Customer instead of Stripe minting a new
    # one every time), not something Phase 2 itself depends on.
    stripe_customer_id = Column(String, nullable=True, index=True)


class RoleFamilyOption(Base):
    """Setup form dropdown data (GET /v1/config/options), backed by a real
    table instead of a hardcoded Python list - editable in the DB without a
    code deploy. `value` must keep matching whatever
    roundzero.interviewers.ml_system_design.agent.pick_scenario and
    prompts/interviewers/ml_system_design/scenarios.yaml expect, same coupling
    as before, just no longer enforced by literally being the same Python
    list (see apps/api/seed.py for the default rows and why they still
    exist)."""

    __tablename__ = "role_family_options"

    value = Column(String, primary_key=True)
    label = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)


class LevelOption(Base):
    """Same pattern as RoleFamilyOption - `value` must match the `level`
    slugs scenarios.yaml's scenarios use (senior/staff/principal)."""

    __tablename__ = "level_options"

    value = Column(String, primary_key=True)
    label = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)


class DomainOption(Base):
    """Same pattern as RoleFamilyOption - `value` must match the `domain`
    slugs scenarios.yaml's scenarios use (ml_infra/general_ml). Named
    DomainOption (not Domain) to avoid any confusion with roundzero.domain,
    the unrelated core-contracts package."""

    __tablename__ = "domain_options"

    value = Column(String, primary_key=True)
    label = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)


class CompanyProfileOption(Base):
    """Same pattern as RoleFamilyOption - `value` becomes RoundAttempt.company_profile.
    `tier` is a cosmetic-only interview-complexity grouping (frontier-ai-labs /
    big-tech / growth-stage / early-stage / enterprise-other) an admin can tag
    each company with - it does not change interviewer behavior, rubric
    weighting, or anything the candidate actually experiences. That's a
    deliberate, separate, much bigger project (a real per-tier interviewer
    persona/prompt) that hasn't been decided on yet - see the tier constant
    list in apps/web/lib/companyTiers.ts."""

    __tablename__ = "company_profile_options"

    value = Column(String, primary_key=True)
    label = Column(String, nullable=False)
    tier = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)


class DurationOption(Base):
    """Same pattern as RoleFamilyOption, but the dropdown value *is* the label
    (minutes) - no separate display text needed."""

    __tablename__ = "duration_options"

    minutes = Column(Integer, primary_key=True)
    sort_order = Column(Integer, nullable=False, default=0)


class RoundTypeOption(Base):
    """Which round types show up on Setup and how (GET /v1/config/options'
    round_types), admin-editable (GET/PUT /v1/admin/round-types) instead of
    the frontend's old hardcoded COMING_SOON_ROUNDS/LOOP_ROUNDS arrays.
    `enabled=True` on "ml_system_design" means the real Start Interview form
    shows; disabling it shows a "temporarily unavailable" notice instead (an
    admin lever for e.g. a provider outage, not just cosmetic) - see
    apps/api/routes/rounds.py's start_round. `enabled` on every OTHER round
    type is display-only: none of them have a real interviewer built yet
    (only roundzero.interviewers.ml_system_design exists), so toggling one on
    changes its badge from "coming soon" to listed-as-available but does NOT
    make it actually startable - Setup's form stays hardcoded to
    ml_system_design regardless, on purpose, until a real interviewer for
    another round type ships."""

    __tablename__ = "round_type_options"

    value = Column(String, primary_key=True)
    label = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)


class StudyResource(Base):
    """Admin-curated prep material (books/courses/papers/links/videos) per
    rubric dimension, shown on /report as a candidate's weakest dimensions'
    "Next suggested action" - see apps/api/routes/report.py. Deliberately not
    seeded with any starter content (apps/api/seed.py) - inventing specific
    book/course titles isn't something to fabricate; this table starts empty
    and only ever holds what an admin actually adds via /admin."""

    __tablename__ = "study_resources"

    id = Column(String, primary_key=True, default=_uuid)
    dimension = Column(String, nullable=False, index=True)  # rubric dimension key, e.g. "reliability"
    round_type = Column(String, nullable=False, default="ml_system_design")
    kind = Column(String, nullable=False, default="link")  # book | course | paper | video | link
    title = Column(String, nullable=False)
    url = Column(String, nullable=True)
    note = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_now)


class AppSetting(Base):
    """Tiny global key/value store for admin-configured settings that don't
    warrant their own table - today just "consultancy_booking_url" (the
    external link behind /report's "Book consultancy with me"). Admin-only to
    write (PUT /v1/admin/settings); GET /v1/settings/public exposes only the
    specific keys candidates are meant to see, never the whole table."""

    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class LoopAttempt(Base):
    """Was a trivial single-round wrapper (milestone-1.md Decision 1); now the
    real multi-round Loop Planner (specs/002 P0.1) has landed - a loop is
    created with one or more PlannedRound entries up front (apps/api/routes/
    loops.py POST /v1/loops), and `name` is user-supplied at that point.
    Nullable at the column level only because 10 pre-feature rows exist with
    no name - see apps/api/migrations/0001_loops_and_tiers.py, which backfills
    those from their own round's real role/level/company data (not invented)
    and every new loop always sets it going forward."""

    __tablename__ = "loop_attempts"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)


class RoundAttempt(Base):
    __tablename__ = "round_attempts"

    id = Column(String, primary_key=True, default=_uuid)
    loop_attempt_id = Column(String, ForeignKey("loop_attempts.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    round_type = Column(String, nullable=False, default="ml_system_design")
    # "text" | "voice" | "both" - chosen at Setup time (StartRoundRequest.mode).
    # Orthogonal to round_type: gates whether the voice/token endpoint and the
    # LiveKit Agents worker (src/roundzero/realtime/) are available for this
    # round. Defaults to "text" so every existing round stays exactly as it was.
    modality = Column(String, nullable=False, default="text")
    role_family = Column(String, nullable=False)
    level = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    company_profile = Column(String, nullable=False, default="generic")
    duration_minutes = Column(Integer, nullable=False)

    scenario_id = Column(String, nullable=False)
    scenario_prompt = Column(String, nullable=False)
    # Structured scenario data beyond the plain prompt string - Coding needs
    # title/constraints/entry_point/starter_code/test_cases (see
    # prompts/interviewers/coding/scenarios.yaml); ml_system_design has no use
    # for this yet and leaves it null. Generic JSON blob rather than a
    # round-type-specific set of columns, same "don't special-case a second
    # round type into the schema" call as everything else in this pass - see
    # apps/api/migrations/0002_coding_round.py.
    scenario_meta = Column(JSON, nullable=True)

    # RoundState (domain/enums.py) as a plain string column - CREATED -> READY ->
    # CHECK_IN -> ACTIVE -> WRAP_UP -> SUBMITTED -> EVALUATING -> EVALUATED
    status = Column(String, nullable=False, default="CREATED")
    phase = Column(String, nullable=False, default="INTRO")
    coverage = Column(JSON, nullable=False, default=dict)

    started_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

    # Set when this round was started by picking a specific question off the
    # candidate's own PrepPlan (apps/web/app/prep-plans/[id]/page.tsx) rather
    # than via pick_scenario()'s random choice - see
    # orchestrator.start_round_from_plan_question and _start_round's
    # scenario_override param. Null for every round started the normal way.
    # Used to compute each question's live progress badge (attempt count +
    # latest status) - never stored redundantly on the question itself, same
    # "compute at read time" discipline as real_interview_prediction.
    prep_plan_question_id = Column(String, ForeignKey("prep_plan_questions.id"), nullable=True, index=True)

    # Set when this round was started via "Practice this weakness" on a past
    # round's report (apps/web/app/reports/[roundId]/page.tsx) rather than
    # picked normally - see orchestrator.start_drill_round. Holds a short
    # human-readable focus note ("system_design_depth: Practice going deeper
    # on failure-mode tradeoffs...") built from that prior round's
    # EvaluationRecord.improvement_plan. Passed to every interviewer.next_turn
    # call for this round (_start_round's opening turn and post_message's
    # continuations) as focus_hint, so the interviewer probes that competency
    # harder across the whole round. Null for every round started normally.
    drill_focus_hint = Column(String, nullable=True)


class PlannedRound(Base):
    """One entry in a loop's planned shape (specs/002 P0.1 Loop Planner),
    created up front when the loop itself is created (apps/api/routes/
    loops.py POST /v1/loops) - before anyone has necessarily started it.
    `round_attempt_id` is null until the candidate actually starts this
    specific round (orchestrator.start_planned_round), at which point it
    points at the real RoundAttempt row created at that moment - never
    created eagerly, since starting a round means calling the real
    interviewer for an opening turn (see orchestrator.create_round's
    docstring) and nothing here should fabricate that ahead of time.

    Every RoundAttempt, old and new, has exactly one PlannedRound wrapping
    it: orchestrator.create_round (the original single-round path) writes
    one alongside the round it creates, and the 10 pre-feature RoundAttempt
    rows were backfilled one each by apps/api/migrations/0001_loops_and_tiers.py.
    This means list/read code never has to special-case "a round with no
    planned-round row" - there isn't one.

    Only round_type == "ml_system_design" has a real interviewer
    (orchestrator.REAL_ROUND_TYPES) - every other round_type can still be
    planned into a loop (the candidate picks all 7 when building one, see
    apps/web/app/loops/new/page.tsx) but start_planned_round rejects
    starting it with a 400, and the frontend disables that row's Start
    button rather than hiding the round - same "show where it's headed,
    don't pretend it works yet" honesty as the old /loop-planner preview."""

    __tablename__ = "planned_rounds"

    id = Column(String, primary_key=True, default=_uuid)
    loop_attempt_id = Column(String, ForeignKey("loop_attempts.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    round_type = Column(String, nullable=False)
    role_family = Column(String, nullable=False)
    level = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    company_profile = Column(String, nullable=False, default="generic")
    duration_minutes = Column(Integer, nullable=False)
    modality = Column(String, nullable=False, default="text")
    sort_order = Column(Integer, nullable=False, default=0)

    round_attempt_id = Column(String, ForeignKey("round_attempts.id"), nullable=True)
    created_at = Column(DateTime, default=_now)


class CandidateProfile(Base):
    """Candidate self-description (PRD section 19's CandidateProfile, docs/PRD.md
    line 327), editable from /profile. Deliberately separate from the
    per-round TargetRole fields on RoundAttempt (role_family/level/domain/
    company_profile, chosen fresh at each round's Setup): this is who the
    candidate says they are and what they're aiming for, independent of any
    one round, and persists across every round they ever start. One row per
    user, upserted in place - no history/versioning, the PRD doesn't call for
    it. linkedin_url is captured now at the candidate's own request but not
    yet read by any interviewer/report/personalization logic - parsing a real
    LinkedIn profile into the interview or report is future scope, not this
    pass."""

    __tablename__ = "candidate_profiles"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    current_role = Column(String, nullable=True)
    target_role = Column(String, nullable=True)
    years_experience = Column(Integer, nullable=True)
    experience_summary = Column(String, nullable=True)
    objective = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class TranscriptTurn(Base):
    """Append-only per CLAUDE.md's working conventions - rows are never mutated or
    deleted, only inserted in order (`turn_index`)."""

    __tablename__ = "transcript_turns"

    id = Column(String, primary_key=True, default=_uuid)
    round_id = Column(String, ForeignKey("round_attempts.id"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False)
    speaker = Column(String, nullable=False)  # "interviewer" | "candidate"
    text = Column(String, nullable=False)
    phase = Column(String, nullable=False)
    competency_tags = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now)


class RoundWorkspaceState(Base):
    """One row per round - the persisted, upsertable state of the split-screen
    workspace panel (Coding's editor buffer, System Design's Excalidraw scene).
    Distinct from TranscriptTurn (append-only chat history): this is "current
    state", overwritten in place, so a reconnect can restore exactly what the
    candidate had on screen. `canvas_summary` is the compact semantic text
    apps/web/lib/workspace/summarizeScene.ts derives client-side from
    `canvas_scene` - orchestrator.py forwards it to the interviewer as
    workspace_context so Gemini can react to the diagram without ever being
    sent raw Excalidraw element JSON."""

    __tablename__ = "round_workspace_states"

    round_id = Column(String, ForeignKey("round_attempts.id"), primary_key=True)
    code_language = Column(String, nullable=True)
    code_text = Column(String, nullable=True)
    canvas_scene = Column(JSON, nullable=True)
    canvas_summary = Column(String, nullable=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class WorkspaceEvent(Base):
    """Append-only audit trail alongside RoundWorkspaceState's "current state" -
    the second event type TranscriptTurn's own docstring anticipated generalizing
    toward. One row per meaningful workspace action (debounced code edits, run
    attempts, test results, final submission, canvas edits), kept even after
    RoundWorkspaceState is overwritten, for later evaluation/replay."""

    __tablename__ = "workspace_events"

    id = Column(String, primary_key=True, default=_uuid)
    round_id = Column(String, ForeignKey("round_attempts.id"), nullable=False, index=True)
    kind = Column(String, nullable=False)  # code_change | run_attempt | test_result | final_submission | canvas_change
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now)


class EvaluationRecord(Base):
    """One row per evaluated round - the persisted form of
    roundzero.evaluation.models.RoundEvaluation (apps/api/orchestrator.py composes
    and stores it after submit)."""

    __tablename__ = "evaluations"

    round_id = Column(String, ForeignKey("round_attempts.id"), primary_key=True)
    dimension_scores = Column(JSON, nullable=False)
    readiness_pct = Column(Integer, nullable=False)
    hire_signal = Column(String, nullable=False)
    primary_concern = Column(String, nullable=False)
    strengths = Column(JSON, nullable=False)
    weaknesses = Column(JSON, nullable=False)
    improvement_plan = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_now)


class LoopCommitteeRecord(Base):
    """Cached Virtual Hiring Committee synthesis for a loop (specs/002-full-loop-platform
    P0.6) - one row per loop, keyed by loop_attempt_id. Regenerated (not appended)
    whenever the set of evaluated real rounds in the loop changes; `rounds_included`
    holds the round_attempt_id list the current row was built from, so
    orchestrator.get_committee_report can tell a cached row is stale without
    re-running the LLM call just to find out (see orchestrator.py's
    get_committee_report/generate_committee_report docstrings).

    Deliberately does NOT store a calibrated level range (e.g. "Strong Senior ->
    Staff") - that is P0.4's job (Level Calibration against explicit
    level-expectation definitions), which doesn't exist yet. `level_signal` here is
    a plain, evidence-grounded directional read instead - see
    src/roundzero/debrief/committee.py's module docstring for why."""

    __tablename__ = "loop_committee_reports"

    loop_attempt_id = Column(String, ForeignKey("loop_attempts.id"), primary_key=True)
    rounds_included = Column(JSON, nullable=False)  # sorted list of round_attempt_id this synthesis covers
    overall_readiness_pct = Column(Integer, nullable=False)
    overall_hire_signal = Column(String, nullable=False)
    confidence = Column(String, nullable=False)  # "medium" | "high" - see committee.py
    headline = Column(String, nullable=False)
    strengths = Column(JSON, nullable=False)
    concerns = Column(JSON, nullable=False)
    level_signal = Column(String, nullable=False)
    key_evidence = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class RealInterviewExperience(Base):
    """A candidate's own log of a real interview they went through at an actual
    company (specs/002-full-loop-platform P0.11) - distinct from every other
    table in this file, which is all about *simulated* rounds. `company` is a
    free-text real name ("Anthropic", "Ramp"), NOT CompanyProfileOption's
    `generic|big_tech|startup` difficulty bucket (apps/api/seed.py) - that
    field flavors simulated scenarios and has nothing to do with which real
    company someone interviewed at. `role_family`/`level` do reuse the
    existing admin-editable option tables, same as everywhere else, since
    those describe company-agnostic role/level archetypes and keep real
    records on the same taxonomy as simulated ones (needed for prediction-vs-
    outcome to mean anything - see orchestrator.real_interview_prediction).

    `rounds` is a JSON list of candidate-authored per-round notes
    ({round_type_label, question_family, follow_ups, difficulty}) - one plain
    JSON blob rather than a child table, same "structured-but-varying, never
    queried across users" call RoundAttempt.scenario_meta already made.
    `notes` is the candidate's own freeform dump, kept verbatim forever even
    after AI-structuring runs (src/roundzero/debrief/real_interview.py) - the
    structured `rounds` breakdown is a derived, editable draft, never a
    replacement for what the candidate actually wrote.

    `visibility` is captured and persisted faithfully but is otherwise inert
    in this pass - nothing reads it to surface content across candidates yet;
    real cross-candidate Interview Intel needs moderation/sanitization infra
    this repo doesn't have (see apps/web/app/intel/page.tsx's docstring)."""

    __tablename__ = "real_interview_experiences"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)

    company = Column(String, nullable=False)
    role_family = Column(String, nullable=False)
    level = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    interview_date = Column(DateTime, nullable=False)

    # Candidate's own past simulated loop they believe this real interview
    # corresponds to - explicitly picked by them (apps/web/app/real-interviews/
    # new/page.tsx), never fuzzy-matched by company/role, so a wrong guess can
    # never silently attach one simulation's prediction to a real outcome.
    linked_loop_attempt_id = Column(String, ForeignKey("loop_attempts.id"), nullable=True)

    rounds = Column(JSON, nullable=False, default=list)
    notes = Column(String, nullable=True)
    self_assessment = Column(String, nullable=True)
    visibility = Column(String, nullable=False, default="private")  # private | anonymous | community

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class RealInterviewOutcome(Base):
    """One row per RealInterviewExperience, upserted in place - specs/002
    P0.12. An outcome is reported once and sometimes updated later (e.g.
    "waiting" -> "offer" weeks after the interview), never a history of its
    own, same "current state, overwritten in place" shape as
    RoundWorkspaceState/CandidateProfile. `offered_level` is only meaningful
    when status == "offer" and is voluntarily provided - never inferred."""

    __tablename__ = "real_interview_outcomes"

    experience_id = Column(String, ForeignKey("real_interview_experiences.id"), primary_key=True)
    status = Column(String, nullable=False)  # rejected | advanced | offer | withdrew | no_response
    stage = Column(String, nullable=True)
    target_level = Column(String, nullable=True)
    offered_level = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

class PrepPlan(Base):
    """A candidate-authored prep plan (e.g. "Staff MLE prep") - user-pitched
    feature, not from the P0 backlog: a self-curated set of practice
    questions the candidate picks from deliberately ("what am I in the mood
    to practice today"), instead of always getting a randomly picked
    scenario via pick_scenario(). See PrepPlanArea/PrepPlanQuestion below and
    orchestrator.start_round_from_plan_question.

    Stores its own target role/level/domain/company/duration/mode - the same
    fields StartRoundRequest needs - set once at creation time, so starting
    any question under this plan never re-asks a setup form; it just goes.
    Individual areas/questions deliberately do NOT carry their own
    role/level - they all inherit the plan's single target profile."""

    __tablename__ = "prep_plans"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)

    role_family = Column(String, nullable=False)
    level = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    company_profile = Column(String, nullable=False, default="generic")
    duration_minutes = Column(Integer, nullable=False, default=45)
    mode = Column(String, nullable=False, default="text")

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class PrepPlanArea(Base):
    """One practice area within a PrepPlan (e.g. "Feature stores", "Graph
    coding"), tagged to a real round_type (must be one of
    orchestrator.REAL_ROUND_TYPES) - that tag is what tells
    start_round_from_plan_question which interviewer class to run when a
    question under this area gets picked. `label` is user-given and defaults
    to that round type's config label (RoundTypeOption) at creation time but
    can be renamed freely - it's just a display name, round_type is what's
    load-bearing."""

    __tablename__ = "prep_plan_areas"

    id = Column(String, primary_key=True, default=_uuid)
    plan_id = Column(String, ForeignKey("prep_plans.id"), nullable=False, index=True)
    round_type = Column(String, nullable=False)
    label = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_now)


class PrepPlanQuestion(Base):
    """One specific question within a PrepPlanArea. Two ways it can get
    here, tracked via `source`:

    - "bank": added by browsing that round type's real scenario bank
      (prompts/interviewers/{round_type}/scenarios.yaml via load_scenarios) -
      `scenario_id` points back at that YAML entry's id, and `prompt` is a
      display-only snapshot of its prompt text. Starting this question looks
      the scenario back up by id and runs the *exact* structured scenario
      dict (title/constraints/entry_point/starter_code/test_cases included
      when present) - this is the ONLY source offered for Coding areas,
      since Coding's workspace needs those structured fields to render
      runnable starter code and tests, which a freeform question has no way
      to supply.
    - "custom": the candidate's own freeform prompt (+ optional `notes`).
      `scenario_id` is null. Only offered for prompt-only round types
      (ml_system_design, ml_depth) - never accepted for a Coding area
      (orchestrator.add_custom_prep_plan_question rejects it), since a
      freeform Coding "question" would produce a broken workspace with no
      starter code or tests.
    - "ai": same shape as "custom" (freeform prompt, scenario_id null) but
      originated from a suggest-questions call the candidate chose to add -
      see orchestrator.suggest_prep_plan_questions. Recorded distinctly from
      "custom" only so the UI can show where a question came from; behaves
      identically to "custom" everywhere else, including the same
      Coding-area restriction (suggestions for Coding areas come from the
      bank fallback and get added with source="bank", never "ai")."""

    __tablename__ = "prep_plan_questions"

    id = Column(String, primary_key=True, default=_uuid)
    area_id = Column(String, ForeignKey("prep_plan_areas.id"), nullable=False, index=True)
    prompt = Column(String, nullable=False)
    notes = Column(String, nullable=True)
    source = Column(String, nullable=False)  # bank | custom | ai
    scenario_id = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_now)


class Feedback(Base):
    """Free-text feedback/issue/advice submitted via the floating widget
    mounted globally in apps/web/app/layout.tsx (outside AppShell, so it's
    visible even during an active interview - see apps/web/components/
    FeedbackWidget.tsx). Any authenticated user can submit
    (POST /v1/feedback); the admin-only listing, which joins in the
    submitter's email/name, lives in apps/api/routes/admin.py. No status/
    workflow field on purpose - for a handful of pilot testers, reading
    straight through the list is simpler than triaging it."""

    __tablename__ = "feedback_submissions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String, nullable=False, default="feedback")  # feedback | issue | advice
    message = Column(String, nullable=False)
    page_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)


# --- World-model interviewer (specs/005-world-model-interviewer) -------------
# Append-only event tables (CLAUDE.md: state rebuildable from event history).
# Diagnosis and the path map are recomputed from these on read, so nothing here
# can go stale. All tables are new - Base.metadata.create_all() creates them on
# startup, no ALTER TABLE migration needed.


class WMEvidence(Base):
    """One span-cited evidence item extracted from one candidate answer."""

    __tablename__ = "wm_evidence"

    id = Column(String, primary_key=True, default=_uuid)
    round_id = Column(String, ForeignKey("round_attempts.id"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False)
    dimension = Column(String, nullable=False)
    competency = Column(String, nullable=True)
    criterion = Column(String, nullable=False)
    polarity = Column(String, nullable=False)
    span = Column(String, nullable=True)
    strength = Column(Float, nullable=False)
    extractor_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)


class WMProcessedTurn(Base):
    """Marks a candidate answer as processed by the extractor (even when it
    produced zero evidence), so tracking is idempotent."""

    __tablename__ = "wm_processed_turns"

    id = Column(String, primary_key=True, default=_uuid)
    round_id = Column(String, ForeignKey("round_attempts.id"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False)
    extractor_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)


class WMBeliefSnapshot(Base):
    """Belief (probability over levels per competency) after one answer."""

    __tablename__ = "wm_beliefs"

    id = Column(String, primary_key=True, default=_uuid)
    round_id = Column(String, ForeignKey("round_attempts.id"), nullable=False, index=True)
    turn_index = Column(Integer, nullable=False)
    probs = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_now)


class WMDecision(Base):
    """Follow-up picker output after one answer - logged in shadow AND live
    mode, so Gate 2 can be evaluated offline from real rounds."""

    __tablename__ = "wm_decisions"

    id = Column(String, primary_key=True, default=_uuid)
    round_id = Column(String, ForeignKey("round_attempts.id"), nullable=False, index=True)
    after_turn_index = Column(Integer, nullable=False)
    mode = Column(String, nullable=False)
    chosen_competency = Column(String, nullable=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_now)


class WMRewrite(Base):
    """Flip rewrite - HYPOTHETICAL, never a training label."""

    __tablename__ = "wm_rewrites"

    id = Column(String, primary_key=True, default=_uuid)
    round_id = Column(String, ForeignKey("round_attempts.id"), nullable=False, index=True)
    competency = Column(String, nullable=False)
    turn_index = Column(Integer, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_now)


class WMRetry(Base):
    """A real retried answer - the only true paired-intervention data."""

    __tablename__ = "wm_retries"

    id = Column(String, primary_key=True, default=_uuid)
    round_id = Column(String, ForeignKey("round_attempts.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    turn_index = Column(Integer, nullable=False)
    retry_text = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_now)


# Free-trial/dogfooder/subscribe-gate sizing (claude.ai Project "roundzero" >
# pricing-design.md). Centralized here since apps/api/deps.py (auto-
# provisioning on signup) and apps/api/orchestrator.py (get_entitlement_status,
# _require_quota, select_plan) all need the same numbers and all already
# import this module.
UNSELECTED_PLAN = "unselected"  # sentinel plan value for a self-signup user who hasn't clicked Subscribe yet - see UserEntitlement's docstring, "Subscribe gate" paragraph
TESTER_ROUNDS_INCLUDED = 8  # 2 loops' worth, no expiry
TRIAL_ROUNDS_INCLUDED = 1  # a single round, not a full loop - see UserEntitlement's docstring
TRIAL_WINDOW_DAYS = 7
PAYPERLOOP_PLAN = "payperloop"  # set on UserEntitlement.plan once someone completes a real Pay-per-loop purchase - see apps/api/routes/billing.py


class UserEntitlement(Base):
    """Round-quota entitlement for a user - the single source of truth for
    how many interview rounds they're allowed to start and by when (see
    claude.ai Project "roundzero" > pricing-design.md for the full design).
    One row per user, auto-created on first sight
    (apps/api/deps.py::get_current_user, right alongside the User shadow-
    profile upsert it already does) so every user always has exactly one
    entitlement row to look up - never a missing-row special case.

    cohort is assigned once, at creation time, from TESTER_EMAILS (mirrors
    ADMIN_EMAILS's allowlist pattern exactly - apps/api/deps.py) and is not
    re-derived on later requests even if TESTER_EMAILS changes:
      - "tester": dogfooding/pilot users, manually allowlisted. 8 rounds
        (2 loops' worth), no expiry.
      - "normal": everyone else who just signs up. 1 round, expires 7 days
        after signup - deliberately a single ROUND, not a full loop, so the
        free trial doesn't reward signing up with a second email address for
        an entire extra loop.
      - "paid": set by an admin's manual grant (Phase 1 - no Stripe wired up
        yet) once a plan is purchased outside the app; rounds_included and
        expires_at are set to reflect whatever was granted. Founding
        Members' "no practical ceiling" is just a very large rounds_included
        value here, not special-cased code.

    rounds_used is deliberately NOT a column - it's always computed live by
    counting RoundAttempt rows created since current_period_start, same
    "compute at read time, never store redundantly" discipline as
    real_interview_prediction and PrepPlanQuestion progress. See
    orchestrator.get_entitlement_status.

    expires_at is nullable: null for the tester cohort and for any paid
    grant with no fixed end. Set for the normal-cohort free trial and for
    time-boxed paid plans once real subscription billing exists (Phase 3).
    An already-ACTIVE round is never interrupted by expires_at passing
    mid-interview - only the pre-flight checks (orchestrator._require_quota,
    called from create_loop and _start_round) consult expires_at, so a round
    started before the deadline is grandfathered through to completion.

    Subscribe gate (added 2026-09-29): a brand-new self-signup user (not in
    TESTER_EMAILS or ADMIN_EMAILS) is provisioned with plan=UNSELECTED_PLAN
    and rounds_included=0 - nothing to practice with until they explicitly
    pick a plan (apps/web's /upgrade page -> POST /v1/auth/subscribe ->
    orchestrator.select_plan). Picking "none" is what actually grants the
    free trial described above, and the 7-day window starts at that moment,
    not at signup - so someone who signs up and comes back a week later to
    finally subscribe still gets the full 7 days. Admin and tester accounts
    skip this gate entirely (provisioned with a real plan immediately,
    apps/api/deps.py::_ensure_entitlement) since they're curated accounts,
    not organic self-signups the product needs to convert."""

    __tablename__ = "user_entitlements"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    cohort = Column(String, nullable=False, default="normal")  # "tester" | "normal" | "paid"
    plan = Column(String, nullable=False, default="none")  # "none" | "monthly" | "yearly" | "founding" | "payperloop"
    billing_interval = Column(String, nullable=False, default="none")  # "none" | "monthly" | "yearly" | "one_time"

    rounds_included = Column(Integer, nullable=False, default=1)
    current_period_start = Column(DateTime, default=_now)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class StripeWebhookEvent(Base):
    """One row per Stripe webhook event apps/api/routes/billing.py has
    already processed - Stripe's own delivery guarantee is "at least once,"
    so the same checkout.session.completed event can arrive more than once
    (a retry after a slow response, a redelivery from the dashboard, etc.).
    The webhook handler checks this table by Stripe's own event.id BEFORE
    crediting any rounds, and inserts a row right after - the same
    idempotency pattern Stripe's own docs recommend, backed by this row's id
    being the primary key so a concurrent duplicate delivery collides rather
    than double-processing (see billing.py's IntegrityError handling, same
    shape as apps/api/deps.py's user-upsert race)."""

    __tablename__ = "stripe_webhook_events"

    id = Column(String, primary_key=True)  # Stripe's own event id (evt_...), not a generated uuid - that's the whole point
    event_type = Column(String, nullable=False)
    processed_at = Column(DateTime, default=_now)
