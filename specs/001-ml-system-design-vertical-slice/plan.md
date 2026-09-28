# Plan - 001 ML System Design Vertical Slice

## Candidate setup (UI)

Single simple form, no wizard:
- Target Role (dropdown) - role family, e.g. ML Engineer
- Target Level (dropdown) - e.g. Principal
- Domain (dropdown) - e.g. ML Infrastructure
- Company (dropdown, default "Generic")
- Interview (fixed to "ML System Design" for this slice - no round picker yet)
- Duration (dropdown, 45 or 60 minutes)
- START INTERVIEW button

No Loop Planner needed yet - "Round Configuration" creates a single-round LoopAttempt
directly from this form. The full Loop Planner (configs/loops/*.yaml -> multi-round
LoopPlan) is deferred to the multi-round spec.

## Interview runtime - phase state machine

The interviewer does NOT run as a single freeform "interview the candidate" prompt. It
runs against an explicit phase state machine:

```
INTRO -> REQUIREMENTS -> HIGH_LEVEL_DESIGN -> ML_MODEL_ARCHITECTURE -> DATA_TRAINING ->
SERVING_SCALE -> RELIABILITY -> EVALUATION_MONITORING -> TRADEOFF_DEEP_DIVE -> WRAP_UP
```

Each turn, the interviewer's input extends PRD section 21.1's `conversation_state` with:
- current_phase
- time_remaining_sec
- coverage: per rubric dimension, one of COVERED / WEAK / NOT_COVERED

Coverage is maintained as part of the interviewer's own structured output each turn
(`private_state_update`, PRD section 21.2) rather than a separate LLM call - it's already
reasoning about what's been said, so updating its own coverage map is a cheap side effect
of generating the next utterance. This coverage map is a *scaffold* for the interviewer's
pacing/probing decisions and for the later Evidence Extractor - it is never itself scored
evidence. The Evidence Extractor and Evaluator still run independently, post-hoc, off the
frozen transcript (PRD section 10) - the interviewer does not grade itself.

Phase transitions are coverage- and time-driven, not fixed-duration. Ten phases across a
45-60 min round leaves ~4-6 min/phase on average, so INTRO/WRAP_UP should be short
bookends and the state machine should let the interviewer linger in a phase with weak
coverage rather than mechanically clock-dividing.

Adaptive probing is driven by candidate claims within the current phase - e.g. "I'll
deploy behind Kubernetes with GPU node pools" (a design choice) should provoke "how do you
prevent one tenant monopolizing GPU capacity" (probes an omission - multi-tenancy - implied
but unaddressed by the stated design), not a scripted next question. This behavior quality
is the highest-leverage thing to get right in this slice; the state machine, rubric, and
report are scaffolding around it, not the hard part themselves.

## Rubric v1 (weighted)

Updated from the initial unweighted seed - see rubrics/ml_system_design/v1.yaml.

| Dimension | Weight |
|---|---|
| Problem framing / requirements | 10% |
| High-level architecture | 15% |
| ML/model reasoning | 15% |
| Data/training | 10% |
| Serving/scalability | 15% |
| Reliability | 10% |
| Evaluation/monitoring | 10% |
| Cost/efficiency | 5% |
| Trade-off reasoning | 5% |
| Communication | 5% |

Two deliberate changes from the PRD section 7 dimension list: serving and scale are merged
into one "serving/scalability" dimension (splitting them didn't add signal for a single
rubric), and "communication" is added as a 10th dimension.

Scored internally on the anchored 1-4 scale only - never ask the model for a percentage
directly (see Readiness % below for why this matters).

## Evidence extraction format

An evaluator dimension score is never a bare number. Required shape, per dimension:

```
Reliability - 2/4
Candidate proposed single-region deployment. Regional failure was not considered until
interviewer prompted it. After prompting, candidate proposed active/passive failover but
did not discuss state synchronization or recovery objectives.
```

This is a short narrative synthesized from the dimension's EvidenceItems (PRD Appendix B),
ordered chronologically - initial claim, interviewer probe, candidate's revised/incomplete
answer. The atomic EvidenceItems stay the source of truth (source_ref pointing to
transcript segments); the narrative is a rendering layer produced once per dimension per
round, not hand-written per session.

## Readiness % - must be a deterministic derived value, not a model output

The report mockup shows "Target-level readiness: 72%". This has to be computed
deterministically from the anchored 1-4 dimension scores and their weights (e.g. a
weighted average against level-appropriate thresholds, scaled to 0-100), never asked of
the LLM directly - otherwise it silently violates the rubric's own stated principle
("score internally using anchored 1-4, rather than asking the model to invent a
percentage"). Same for the categorical "Overall Signal" (e.g. LEAN HIRE) - it's a
threshold function over the weighted score plus any role/level criticality rules (PRD
section 10.1's hire-signal scale), not something generated in prose.

## Report - "Primary Concern" headline

The mockup's one-line synthesized concern ("Strong ML architecture reasoning, but
production reliability thinking is currently below Principal-level expectations") is real
logic, not templating - a single-round, single-headline version of what full cross-round
Debrief synthesis will later do (PRD section 11). Decide whether it's rule-based (surface
the largest gap between the highest- and lowest-scoring dimension, weighted toward
critical dimensions) or a small separate LLM synthesis pass over the finished
RoundEvaluation. Either way it should live as its own step after evaluation completes, not
be embedded inside the Evaluator itself (keeps the evaluator narrowly "score with
evidence," per PRD section 10).

## Open questions carried forward

- ~~Exact LLM provider/model for interviewer vs evaluator.~~ Resolved (locked V1
  stack): Gemini 3.6 Flash interviews (GeminiGateway - model bumped 2026-09 from
  2.5 Flash after Google retired it for new API keys), GPT-5 mini evaluates and
  writes the report (OpenAIGateway) - deliberately different vendors, see
  CLAUDE.md decision 4 and apps/api/orchestrator.py's get_gateway()/get_evaluator().
  Both fall back to the mock/rule-based path with no key set.
- Whether the design artifact stays text-only for v0 or gets a minimal diagram upload.
- ~~Rule-based vs LLM-based "Primary Concern" synthesis (new, see above).~~
  Resolved: both exist behind the same interface - LLM-based
  (roundzero.debrief.synthesis.llm_report_synthesis, GPT-5 mini) when
  OPENAI_API_KEY is set, rule-based otherwise.
- Who authors the 10 required scenario seeds (tasks.md, item 4).
