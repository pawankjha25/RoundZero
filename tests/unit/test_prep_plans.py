"""
Prep Plans - user-pitched feature (not from the P0 backlog): a candidate's
own self-curated prep plan, organized into areas each holding a list of
practice questions picked deliberately instead of pick_scenario()'s random
choice. Covers orchestrator.create_prep_plan/list_.../get_owned_.../
update_.../delete_..., area + question CRUD (including the Coding
freeform-authoring restriction), start_round_from_plan_question (proves it
actually runs a round against the exact requested scenario, using
REAL_ROUND_TYPES' own interviewers with no LLM key - same "no network"
convention as test_coding_round_e2e.py), and question_progress.

Same isolated-private-engine pattern as test_real_interviews.py/
test_loop_delete.py - this file's rows never touch any other test file's
data no matter collection order.
"""
from __future__ import annotations

import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api import orchestrator
from apps.api.db import Base
from apps.api.models import PlannedRound
from apps.api.schemas import AddBankQuestionIn, AddCustomQuestionIn, PrepPlanAreaIn, PrepPlanIn
from roundzero.prep_plan.suggest import SuggestedQuestion

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)


def _plan_req(**overrides) -> PrepPlanIn:
    defaults = dict(
        name="Staff MLE prep",
        role_family="ml_engineer",
        level="staff",
        domain="ml_infra",
        company_profile="generic",
        duration_minutes=45,
        mode="text",
    )
    defaults.update(overrides)
    return PrepPlanIn(**defaults)


def test_create_list_get_update_delete_round_trip():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u1", _plan_req())
        assert plan.name == "Staff MLE prep"

        listed = orchestrator.list_prep_plans(db, "u1")
        assert [p.id for p in listed] == [plan.id]

        fetched = orchestrator.get_owned_prep_plan(db, "u1", plan.id)
        assert fetched is not None and fetched.id == plan.id

        updated = orchestrator.update_prep_plan(db, plan, _plan_req(name="Renamed plan"))
        assert updated.name == "Renamed plan"

        orchestrator.delete_prep_plan(db, updated)
        assert orchestrator.get_owned_prep_plan(db, "u1", plan.id) is None
    finally:
        db.close()


def test_plan_ownership_check_blocks_a_different_user():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u2", _plan_req())
        assert orchestrator.get_owned_prep_plan(db, "someone-else", plan.id) is None
        assert orchestrator.get_owned_prep_plan(db, "u2", "not-a-real-id") is None
    finally:
        db.close()


def test_add_area_rejects_a_round_type_with_no_real_interviewer():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u3", _plan_req())
        with pytest.raises(orchestrator.RoundTypeNotAvailableError):
            orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="behavioral", label="Behavioral"))
    finally:
        db.close()


def test_area_and_question_ownership_checks_block_a_different_user():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u4", _plan_req())
        area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="ml_system_design", label="System Design"))
        question = orchestrator.add_custom_prep_plan_question(
            db, area, AddCustomQuestionIn(prompt="Design a rate limiter.")
        )

        assert orchestrator.get_owned_prep_plan_area(db, "someone-else", area.id) is None
        assert orchestrator.get_owned_prep_plan_question(db, "someone-else", question.id) is None
        assert orchestrator.get_owned_prep_plan_area(db, "u4", area.id) is not None
        assert orchestrator.get_owned_prep_plan_question(db, "u4", question.id) is not None
    finally:
        db.close()


def test_add_custom_question_is_rejected_for_a_coding_area():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u5", _plan_req())
        coding_area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="coding", label="Coding"))
        with pytest.raises(orchestrator.CustomQuestionNotAllowedError):
            orchestrator.add_custom_prep_plan_question(db, coding_area, AddCustomQuestionIn(prompt="Reverse a linked list."))
    finally:
        db.close()


def test_add_question_from_bank_works_for_every_round_type_including_coding():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u6", _plan_req())
        coding_area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="coding", label="Coding"))

        bank = orchestrator.list_bank_scenarios_for_area(db, coding_area)
        assert len(bank) > 0
        scenario_id = bank[0]["id"]

        question = orchestrator.add_prep_plan_question_from_bank(db, coding_area, scenario_id)
        assert question.source == "bank"
        assert question.scenario_id == scenario_id
        assert question.prompt == bank[0]["prompt"]
    finally:
        db.close()


def test_add_question_from_bank_rejects_an_unknown_scenario_id():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u7", _plan_req())
        area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="coding", label="Coding"))
        with pytest.raises(orchestrator.BankScenarioNotFoundError):
            orchestrator.add_prep_plan_question_from_bank(db, area, "not-a-real-scenario-id")
    finally:
        db.close()


def test_delete_plan_cascades_areas_and_questions():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u8", _plan_req())
        area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="ml_depth", label="ML Depth"))
        question = orchestrator.add_custom_prep_plan_question(db, area, AddCustomQuestionIn(prompt="Explain dropout."))
        # Capture ids before deleting - the ORM objects themselves become
        # detached once delete_prep_plan's cascade removes their rows, so
        # reading an attribute off them afterward (rather than off the id
        # captured beforehand) would itself raise DetachedInstanceError.
        area_id, question_id = area.id, question.id

        orchestrator.delete_prep_plan(db, plan)

        from apps.api.models import PrepPlanArea, PrepPlanQuestion

        assert db.get(PrepPlanArea, area_id) is None
        assert db.get(PrepPlanQuestion, question_id) is None
    finally:
        db.close()


def test_suggest_questions_uses_bank_fallback_for_coding_and_for_freeform_types_with_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u9", _plan_req())
        coding_area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="coding", label="Coding"))
        design_area = orchestrator.add_prep_plan_area(
            db, plan, PrepPlanAreaIn(round_type="ml_system_design", label="System Design")
        )

        coding_suggestions = orchestrator.suggest_prep_plan_questions(db, coding_area)
        design_suggestions = orchestrator.suggest_prep_plan_questions(db, design_area)

        assert len(coding_suggestions) > 0 and all(s.scenario_id for s in coding_suggestions)
        assert len(design_suggestions) > 0 and all(s.scenario_id for s in design_suggestions)
    finally:
        db.close()


def test_add_suggested_question_from_bank_gets_source_bank_and_freeform_gets_source_ai():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u10", _plan_req())
        area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="ml_system_design", label="System Design"))

        bank = orchestrator.list_bank_scenarios_for_area(db, area)
        bank_suggestion = SuggestedQuestion(prompt=bank[0]["prompt"], notes="", scenario_id=bank[0]["id"])
        added_bank = orchestrator.add_suggested_prep_plan_question(db, area, bank_suggestion)
        assert added_bank.source == "bank"
        assert added_bank.scenario_id == bank[0]["id"]

        freeform_suggestion = SuggestedQuestion(prompt="Design a real-time recommendation cache.", notes="hint", scenario_id=None)
        added_ai = orchestrator.add_suggested_prep_plan_question(db, area, freeform_suggestion)
        assert added_ai.source == "ai"
        assert added_ai.scenario_id is None
        assert added_ai.notes == "hint"
    finally:
        db.close()


def test_start_round_from_plan_question_raises_for_unowned_or_missing_question():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u11", _plan_req())
        area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="ml_system_design", label="System Design"))
        question = orchestrator.add_custom_prep_plan_question(db, area, AddCustomQuestionIn(prompt="Design a rate limiter."))

        with pytest.raises(orchestrator.PlanQuestionNotFoundError):
            orchestrator.start_round_from_plan_question(db, "someone-else", question.id)
        with pytest.raises(orchestrator.PlanQuestionNotFoundError):
            orchestrator.start_round_from_plan_question(db, "u11", "not-a-real-question-id")
    finally:
        db.close()


def test_start_round_from_a_custom_question_runs_against_the_exact_requested_prompt():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u12", _plan_req())
        area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="ml_system_design", label="System Design"))
        question = orchestrator.add_custom_prep_plan_question(
            db, area, AddCustomQuestionIn(prompt="Design a URL shortener for 1B requests/day.")
        )

        round_, first_turn = orchestrator.start_round_from_plan_question(db, "u12", question.id)

        assert round_.prep_plan_question_id == question.id
        assert round_.scenario_prompt == "Design a URL shortener for 1B requests/day."
        assert round_.role_family == plan.role_family
        assert round_.level == plan.level
        assert round_.domain == plan.domain
        assert round_.round_type == "ml_system_design"
        assert first_turn.speaker == "interviewer"

        progress = orchestrator.question_progress(db, question.id)
        assert progress.attempts == 1
        # Not yet evaluated (round just started) - readiness fields stay None.
        assert progress.latest_readiness_pct is None

        # create_round's own invariant ("every RoundAttempt has exactly one
        # PlannedRound, no special-casing needed elsewhere") must hold here
        # too - this entrypoint creates its own fresh loop exactly like
        # create_round does. Missing this left the loop with 0 planned
        # rounds even though a real round had been started and attempted,
        # which the dashboard then showed as a confusing
        # "0 of 0 interviews started" entry under Upcoming (caught live
        # 2026-09-03).
        planned = db.query(PlannedRound).filter(PlannedRound.round_attempt_id == round_.id).one_or_none()
        assert planned is not None
        assert planned.loop_attempt_id == round_.loop_attempt_id
    finally:
        db.close()


def test_start_round_from_a_bank_question_runs_against_the_exact_bank_scenario():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u13", _plan_req(role_family="software_engineer"))
        area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="coding", label="Coding"))
        bank = orchestrator.list_bank_scenarios_for_area(db, area)
        question = orchestrator.add_prep_plan_question_from_bank(db, area, bank[0]["id"])

        round_, _first_turn = orchestrator.start_round_from_plan_question(db, "u13", question.id)

        assert round_.prep_plan_question_id == question.id
        assert round_.scenario_id == bank[0]["id"]
        assert round_.scenario_prompt == bank[0]["prompt"]
        # Coding's structured fields (title/entry_point/starter_code/test_cases)
        # must have landed on scenario_meta, same as any other coding round -
        # proves start_round_from_plan_question looked the scenario back up
        # fresh from the bank rather than trusting the question's own prompt
        # column, which carries no structured fields.
        assert round_.scenario_meta.get("entry_point")
    finally:
        db.close()


def test_question_progress_is_zero_before_any_attempt():
    db = SessionLocal()
    try:
        plan = orchestrator.create_prep_plan(db, "u14", _plan_req())
        area = orchestrator.add_prep_plan_area(db, plan, PrepPlanAreaIn(round_type="ml_depth", label="ML Depth"))
        question = orchestrator.add_custom_prep_plan_question(db, area, AddCustomQuestionIn(prompt="Explain attention."))

        progress = orchestrator.question_progress(db, question.id)
        assert progress.attempts == 0
        assert progress.latest_status is None
    finally:
        db.close()
