"""
End-to-end verification for the Coding round type (specs/004-coding-round-type):
proves the full start -> message -> submit -> evaluate loop actually works for
round_type="coding", using the real CodingInterviewer, the real
rubrics/coding/v1.yaml + prompts/interviewers/coding/scenarios.yaml, and the
real RuleBasedEvaluator - only the LLM call itself is faked (no network/API
key), same "no network" convention as
test_orchestrator_interviewer_unavailable.py, whose isolated-tmp-DB pattern
this file also follows.

Specifically proves the generalization work in this pass actually wired
through, not just that the new files parse:
- orchestrator.start_planned_round()/_start_round() can start a "coding"
  PlannedRound (previously only ml_system_design was in REAL_ROUND_TYPES).
- The real CodingInterviewer.pick_scenario() selects a real seed and its
  structured fields land on RoundAttempt.scenario_meta (title/entry_point/
  starter_code_python/test_cases) - what CodingWorkspace.tsx now renders from.
- ConversationState/RoundAttempt.coverage starts from CODING's own rubric
  dimension keys (rubrics/coding/v1.yaml), not ml_system_design's - the
  _default_coverage_for() fix.
- post_message() picks CodingInterviewer (not MLSystemDesignInterviewer) by
  round_type, and _workspace_context() reads the code editor buffer
  (RoundWorkspaceState.code_text) instead of a canvas_summary.
- submit_round()'s RuleBasedEvaluator scores against coding's own 8
  dimensions, not ml_system_design's 10.
- LLMEvaluator.evaluate() and llm_report_synthesis() (checked directly, since
  submit_round only calls them when OPENAI_API_KEY is set) load the coding-
  specific evaluator/report prompts instead of hardcoded "ml_system_design".
"""
from __future__ import annotations

import json
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api import orchestrator
from apps.api.db import Base
from apps.api.models import LoopAttempt, PlannedRound, RoundAttempt
from apps.api.schemas import LoopCreateRequest, PlannedRoundIn
from roundzero.debrief.synthesis import llm_report_synthesis
from roundzero.domain.enums import Phase
from roundzero.evaluation.evaluator import LLMEvaluator
from roundzero.evaluation.rubric_loader import rubric_dimension_keys
from roundzero.llm.gateway import LLMGateway

# A fully private engine/session, same pattern as test_admin_and_report.py -
# NOT the "set DATABASE_URL before importing apps.api.db" pattern older files
# here use, which tests/conftest.py's own docstring documents as fragile
# (apps.api.db.engine/SessionLocal are a process-wide singleton bound at
# whichever test file imports apps.api.db first; a later os.environ write is
# too late to matter). Building our own engine sidesteps that race and the
# shared-conftest-db row leakage it causes entirely - this file's rows never
# touch any other test file's data no matter the collection order.
_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)

CODING_DIMS = rubric_dimension_keys("coding")
ML_DIMS = rubric_dimension_keys("ml_system_design")

_CODING_PHASE_SEQUENCE = [
    Phase.CLARIFYING_QUESTIONS,
    Phase.APPROACH,
    Phase.IMPLEMENTATION,
    Phase.TESTING_DEBUGGING,
    Phase.COMPLEXITY_TRADEOFFS,
    Phase.WRAP_UP,
]


class CodingScriptGateway(LLMGateway):
    """Deterministic fake, same spirit as MockLLMGateway but scripted against
    CODING's own phases/dimensions (proves this test isn't accidentally
    passing off ml_system_design's shape) rather than reusing the real
    MockLLMGateway, which is hardcoded to ml_system_design (a real, separate,
    lower-priority gap noted for follow-up - it only affects the no-API-key
    fallback path, which the user's real .env doesn't exercise)."""

    def __init__(self):
        self._turn = 0

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        index = min(self._turn, len(_CODING_PHASE_SEQUENCE) - 1)
        phase = _CODING_PHASE_SEQUENCE[index]
        self._turn += 1

        coverage = {dim: "NOT_COVERED" for dim in CODING_DIMS}
        covered_so_far = CODING_DIMS[: min(index + 1, len(CODING_DIMS))]
        for dim in covered_so_far:
            coverage[dim] = "WEAK"

        return json.dumps(
            {
                "utterance": f"(scripted turn {index} for phase {phase.value})",
                "action": "WRAP" if phase == Phase.WRAP_UP else "ASK",
                "competency_tags": covered_so_far[-1:],
                "phase": phase.value,
                "coverage": coverage,
            }
        )


def _fresh_db():
    return SessionLocal()


def test_coding_round_starts_with_a_real_scenario_and_coding_shaped_coverage(monkeypatch):
    monkeypatch.setattr(orchestrator, "get_gateway", lambda **kwargs: CodingScriptGateway())

    db = _fresh_db()
    try:
        before_rounds = db.query(RoundAttempt).count()
        before_loops = db.query(LoopAttempt).count()

        loop = orchestrator.create_loop(
            db,
            "coding-test-user",
            LoopCreateRequest(
                name="Coding E2E Test Loop",
                role_family="ml_engineer",
                level="senior",
                domain="ml_infra",
                company_profile="generic",
                mode="text",
                rounds=[PlannedRoundIn(round_type="coding", duration_minutes=45)],
            ),
        )
        planned = db.query(PlannedRound).filter(PlannedRound.loop_attempt_id == loop.id).one()
        assert planned.round_attempt_id is None  # planning != starting

        round_, opening_turn = orchestrator.start_planned_round(db, "coding-test-user", planned.id)

        # 1. Real round_type dispatch - coding actually started, not silently
        #    treated as ml_system_design.
        assert round_.round_type == "coding"
        assert round_.status == "ACTIVE"

        # 2. A real seed scenario was picked (prompts/interviewers/coding/
        #    scenarios.yaml) and its structured fields landed on scenario_meta -
        #    what CodingWorkspace.tsx now renders the problem panel from.
        assert round_.scenario_id  # e.g. "two_sum"
        assert round_.scenario_prompt
        assert round_.scenario_meta is not None
        assert round_.scenario_meta.get("title")
        assert round_.scenario_meta.get("entry_point")
        assert round_.scenario_meta.get("starter_code_python")
        assert isinstance(round_.scenario_meta.get("test_cases"), list)
        assert len(round_.scenario_meta["test_cases"]) > 0

        # 3. Coverage started from CODING's own rubric dimensions, not
        #    ml_system_design's - _default_coverage_for()'s whole point.
        assert set(round_.coverage.keys()) <= set(CODING_DIMS)
        assert not (set(round_.coverage.keys()) & set(ML_DIMS) - set(CODING_DIMS))

        # 4. Opening turn is real and persisted.
        assert opening_turn.speaker == "interviewer"
        assert opening_turn.text

        # 5. post_message() picks CodingInterviewer by round_type (not always
        #    MLSystemDesignInterviewer) and _workspace_context reads code_text.
        reply_turn = orchestrator.post_message(db, round_, "I'd start by clarifying the input constraints.")
        assert reply_turn.speaker == "interviewer"
        db.refresh(round_)
        assert round_.phase in {p.value for p in _CODING_PHASE_SEQUENCE}

        # 6. submit_round()'s RuleBasedEvaluator (no OPENAI_API_KEY in this
        #    test process) scores against coding's own 8 dimensions.
        evaluation = orchestrator.submit_round(db, round_)
        scored_dims = {d.dimension for d in evaluation.dimension_scores}
        assert scored_dims == set(CODING_DIMS)
        assert scored_dims.isdisjoint(set(ML_DIMS) - set(CODING_DIMS))
        assert 0 <= evaluation.readiness_pct <= 100
        assert evaluation.hire_signal

        after_rounds = db.query(RoundAttempt).count()
        after_loops = db.query(LoopAttempt).count()
        assert after_rounds == before_rounds + 1
        assert after_loops == before_loops + 1
    finally:
        db.close()


class RecordingGateway(LLMGateway):
    """Captures the `system` prompt it was called with so the test can assert
    which prompt file actually got loaded, without needing a real model."""

    def __init__(self, response: dict):
        self.seen_system_prompts: list[str] = []
        self._response = response

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        self.seen_system_prompts.append(system)
        return json.dumps(self._response)


def test_llm_evaluator_loads_the_coding_evaluator_prompt_not_ml_system_design():
    gateway = RecordingGateway(
        {
            "dimension_scores": [
                {"dimension": dim, "score": 3, "evidence_narrative": "scripted"} for dim in CODING_DIMS
            ]
        }
    )
    evaluator = LLMEvaluator(gateway)
    scored = evaluator.evaluate(
        round_id="r1",
        round_type="coding",
        transcript=[{"speaker": "candidate", "text": "hi", "phase": "INTRO", "competency_tags": []}],
        final_coverage={},
    )
    assert {d.dimension for d in scored.dimension_scores} == set(CODING_DIMS)
    assert len(gateway.seen_system_prompts) == 1
    # The coding evaluator persona (prompts/evaluators/coding/v1.md), not the
    # ml_system_design one - proves LLMEvaluator.__init__'s old hardcoded
    # load_evaluator_prompt("ml_system_design", ...) is really gone.
    with open("prompts/evaluators/coding/v1.md", encoding="utf-8") as f:
        coding_prompt_text = f.read()
    assert gateway.seen_system_prompts[0] == coding_prompt_text


def test_llm_report_synthesis_loads_the_coding_report_prompt_not_ml_system_design():
    from roundzero.evaluation.models import DimensionScore

    dims = [
        DimensionScore(dimension=k, label=k, weight=1.0 / len(CODING_DIMS), score=3, evidence_narrative="x", evidence=[])
        for k in CODING_DIMS
    ]
    gateway = RecordingGateway({"primary_concern": "scripted concern", "improvement_plan": []})
    concern, plan = llm_report_synthesis(gateway, dims, round_type="coding")
    assert concern == "scripted concern"
    assert len(gateway.seen_system_prompts) == 1
    with open("prompts/report/coding/v1.md", encoding="utf-8") as f:
        coding_prompt_text = f.read()
    assert gateway.seen_system_prompts[0] == coding_prompt_text


def test_llm_report_synthesis_still_defaults_to_ml_system_design_when_unspecified():
    """Regression guard: existing ml_system_design callers that don't pass
    round_type= must keep getting the exact same prompt as before this pass."""
    from roundzero.evaluation.models import DimensionScore

    dims = [
        DimensionScore(dimension=k, label=k, weight=1.0 / len(ML_DIMS), score=3, evidence_narrative="x", evidence=[])
        for k in ML_DIMS
    ]
    gateway = RecordingGateway({"primary_concern": "scripted concern", "improvement_plan": []})
    llm_report_synthesis(gateway, dims)
    with open("prompts/report/ml_system_design/v1.md", encoding="utf-8") as f:
        ml_prompt_text = f.read()
    assert gateway.seen_system_prompts[0] == ml_prompt_text
