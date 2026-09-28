"""
Shared enums for the interview runtime. See docs/PRD.md section 9 (session states),
section 21 (agent contracts), and specs/001-ml-system-design-vertical-slice/plan.md
(phase state machine).
"""
from enum import Enum


class Phase(str, Enum):
    """Interview phases - shared across round types (ConversationState.phase,
    TranscriptTurn.phase, InterviewerOutput.phase are all this one enum, not a
    per-round-type type), so a new round type adds its own phase members here
    rather than defining a parallel enum. INTRO/WRAP_UP are genuinely shared
    (orchestrator.py's server-side time-up cutoff pattern-matches on them
    regardless of round type); everything else below is one round type's own
    phase sequence - see each one's PHASE_ORDER list and its own interviewer
    prompt (prompts/interviewers/<round_type>/v1.md) for what actually uses
    it. ml_system_design (plan.md) added the first sequence; coding
    (specs/004-coding-round-type) added the second."""

    INTRO = "INTRO"
    # -- ml_system_design (specs/001) --
    REQUIREMENTS = "REQUIREMENTS"
    HIGH_LEVEL_DESIGN = "HIGH_LEVEL_DESIGN"
    ML_MODEL_ARCHITECTURE = "ML_MODEL_ARCHITECTURE"
    DATA_TRAINING = "DATA_TRAINING"
    SERVING_SCALE = "SERVING_SCALE"
    RELIABILITY = "RELIABILITY"
    EVALUATION_MONITORING = "EVALUATION_MONITORING"
    TRADEOFF_DEEP_DIVE = "TRADEOFF_DEEP_DIVE"
    # -- coding (specs/004) --
    CLARIFYING_QUESTIONS = "CLARIFYING_QUESTIONS"
    APPROACH = "APPROACH"
    IMPLEMENTATION = "IMPLEMENTATION"
    TESTING_DEBUGGING = "TESTING_DEBUGGING"
    COMPLEXITY_TRADEOFFS = "COMPLEXITY_TRADEOFFS"
    # -- ml_depth (2026-09-03, candidate-scoped conversational deep-dive) --
    FOUNDATIONS = "FOUNDATIONS"
    DEEP_DIVE = "DEEP_DIVE"
    APPLIED_REASONING = "APPLIED_REASONING"
    DEBUGGING_SCENARIO = "DEBUGGING_SCENARIO"
    BREADTH_CHECK = "BREADTH_CHECK"
    # -- backend_system_design (2026-09-05) -- reuses REQUIREMENTS,
    # HIGH_LEVEL_DESIGN, SERVING_SCALE, RELIABILITY, and TRADEOFF_DEEP_DIVE
    # from ml_system_design's sequence above (none of those five are actually
    # ML-specific despite being introduced there first) plus one new phase
    # for API/data-model design, which ml_system_design's own sequence never
    # needed.
    API_DATA_MODEL = "API_DATA_MODEL"
    # -- technical_leadership (2026-09-05, candidate-scoped behavioral/
    # leadership interview - no canvas, no code, pure conversation) --
    TECHNICAL_VISION = "TECHNICAL_VISION"
    PEOPLE_LEADERSHIP = "PEOPLE_LEADERSHIP"
    CONFLICT_INFLUENCE = "CONFLICT_INFLUENCE"
    DECISION_MAKING = "DECISION_MAKING"
    # -- xfn / Cross-functional (2026-09-05, candidate-scoped conversational
    # round on working across PM/design/data/business stakeholders) --
    STAKEHOLDER_ALIGNMENT = "STAKEHOLDER_ALIGNMENT"
    PRIORITIZATION_TRADEOFFS = "PRIORITIZATION_TRADEOFFS"
    COMMUNICATION_INFLUENCE = "COMMUNICATION_INFLUENCE"
    HANDLING_DISAGREEMENT = "HANDLING_DISAGREEMENT"
    WRAP_UP = "WRAP_UP"


# ml_system_design's own phase sequence - unused elsewhere today (reserved for
# a future progress-bar UI, see spec-003 tasks.md), kept exactly as it was.
PHASE_ORDER = [
    Phase.INTRO,
    Phase.REQUIREMENTS,
    Phase.HIGH_LEVEL_DESIGN,
    Phase.ML_MODEL_ARCHITECTURE,
    Phase.DATA_TRAINING,
    Phase.SERVING_SCALE,
    Phase.RELIABILITY,
    Phase.EVALUATION_MONITORING,
    Phase.TRADEOFF_DEEP_DIVE,
    Phase.WRAP_UP,
]

# coding's own phase sequence - same reserved-for-later status as PHASE_ORDER above.
CODING_PHASE_ORDER = [
    Phase.INTRO,
    Phase.CLARIFYING_QUESTIONS,
    Phase.APPROACH,
    Phase.IMPLEMENTATION,
    Phase.TESTING_DEBUGGING,
    Phase.COMPLEXITY_TRADEOFFS,
    Phase.WRAP_UP,
]

# ml_depth's own phase sequence - same reserved-for-later status as the two above.
ML_DEPTH_PHASE_ORDER = [
    Phase.INTRO,
    Phase.FOUNDATIONS,
    Phase.DEEP_DIVE,
    Phase.APPLIED_REASONING,
    Phase.DEBUGGING_SCENARIO,
    Phase.BREADTH_CHECK,
    Phase.WRAP_UP,
]

# backend_system_design's own phase sequence - same reserved-for-later status
# as the sequences above. Deliberately reuses five of ml_system_design's own
# phases (see the Phase enum's comment on API_DATA_MODEL) rather than
# defining parallel ones, since this round type is the same "design a
# production system end-to-end" shape, minus the ML-specific phases.
BACKEND_SYSTEM_DESIGN_PHASE_ORDER = [
    Phase.INTRO,
    Phase.REQUIREMENTS,
    Phase.API_DATA_MODEL,
    Phase.HIGH_LEVEL_DESIGN,
    Phase.SERVING_SCALE,
    Phase.RELIABILITY,
    Phase.TRADEOFF_DEEP_DIVE,
    Phase.WRAP_UP,
]

# technical_leadership's own phase sequence - same reserved-for-later status.
TECHNICAL_LEADERSHIP_PHASE_ORDER = [
    Phase.INTRO,
    Phase.TECHNICAL_VISION,
    Phase.PEOPLE_LEADERSHIP,
    Phase.CONFLICT_INFLUENCE,
    Phase.DECISION_MAKING,
    Phase.WRAP_UP,
]

# xfn's (Cross-functional) own phase sequence - same reserved-for-later status.
XFN_PHASE_ORDER = [
    Phase.INTRO,
    Phase.STAKEHOLDER_ALIGNMENT,
    Phase.PRIORITIZATION_TRADEOFFS,
    Phase.COMMUNICATION_INFLUENCE,
    Phase.HANDLING_DISAGREEMENT,
    Phase.WRAP_UP,
]


class CoverageStatus(str, Enum):
    NOT_COVERED = "NOT_COVERED"
    WEAK = "WEAK"
    COVERED = "COVERED"


class InterviewerAction(str, Enum):
    """PRD section 21.2 interviewer output action field."""

    ASK = "ASK"
    PROBE = "PROBE"
    CLARIFY = "CLARIFY"
    HINT = "HINT"
    TRANSITION = "TRANSITION"
    WRAP = "WRAP"


class RoundState(str, Enum):
    """PRD section 9 canonical session states (subset relevant to milestone 1)."""

    CREATED = "CREATED"
    READY = "READY"
    CHECK_IN = "CHECK_IN"
    ACTIVE = "ACTIVE"
    WRAP_UP = "WRAP_UP"
    SUBMITTED = "SUBMITTED"
    EVALUATING = "EVALUATING"
    EVALUATED = "EVALUATED"
