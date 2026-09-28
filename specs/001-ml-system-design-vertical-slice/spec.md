# 001 - ML System Design Vertical Slice

## Status
Draft

## Why
This is Phase 1: the first full vertical slice. Candidate setup -> ML System Design
interview -> adaptive AI interviewer -> evidence extraction -> evaluation -> report ->
improvement plan. ML System Design is round #1 because it exercises almost everything
Round Zero ultimately needs (adaptive conversation, structured evidence logging,
rubric-based evaluation, level calibration, evidence-backed reporting) without needing a
coding sandbox or realtime voice, which the PRD's own milestone table (M3, M5) defers
until after a text-only round works end-to-end. Everything else (other round types,
cross-round debrief synthesis, voice, sandbox) is deferred until this slice works.
Once it works, it becomes the template for the remaining round types (PRD section 32).

## Scope

In scope:
- One TargetRole: Principal ML Engineer / ML Infra, principal level
- One round type: ML System Design (PRD section 7)
- Text-only interview (no voice yet - PRD ticket order defers voice, section 37 ticket 14)
- Independent evaluation of that one round (PRD section 10)
- A candidate-facing report for the single completed round (PRD section 37 ticket 10)
- Improvement Planner output scoped to this one round's evidence - competency gaps ->
  prioritized tasks (PRD section 13), not a full-loop synthesis

Out of scope (deferred to later specs):
- Other round types, Loop Planner producing a full multi-round loop, cross-round debrief
  synthesis (not meaningful with only one round live), coding sandbox, realtime voice,
  admin content tooling, billing.

## Functional requirements

Interviewer (PRD section 7, "ML System Design"):
- Conversational interview (whiteboard/canvas can come later - a text description of
  architecture is enough for the first cut)
- Problem requires: requirements gathering, data, features/models, training, serving,
  experimentation, monitoring, reliability, cost
- Interviewer asks adaptive follow-ups based on candidate claims/omissions/contradictions
  (PRD section 8)
- Interviewer never teaches/coaches unless explicitly enabled (PRD section 8)
- Interviewer records a structured evidence log: claim, candidate evidence, interviewer
  probe, outcome, competency tag, timestamp (PRD section 8)
- Server-authoritative session state machine: CREATED -> READY -> CHECK_IN -> ACTIVE ->
  WRAP_UP -> SUBMITTED -> EVALUATING -> EVALUATED (PRD section 9)
- Reconnect restores transcript, timer, and interviewer context without losing persisted
  work (PRD section 9, section 33)

Evaluation (PRD section 10):
- Evidence Extractor maps transcript to competency-tagged evidence
- Primary Evaluator scores the rubric using evidence citations only - no unsupported claims
  (PRD section 21.3, section 26)
- Rubric dimensions for this round: framing, ML architecture, data, modeling, serving,
  scale, reliability, evaluation, cost, trade-offs (PRD section 7)
- Scoring scale: 1-4, anchored (PRD Appendix A / Table 9)
- Required evaluator output: dimension scores, hire signal, level signal + confidence,
  evidence for every material claim, hints received + impact, critical misses vs optional
  improvements, insufficient-evidence flags (PRD section 10.1)

Report (PRD section 12, scoped to a single round):
- Round scorecard, competency heat map, strengths/weaknesses with evidence, representative
  transcript moments

Improvement Plan (PRD section 13, scoped to a single round):
- Inputs: this round's RoundEvaluation (competency gaps), candidate's available hours,
  target interview date
- Output: prioritized task list at a chosen horizon (7/14/21/30 days); each task has an
  objective, expected duration, artifact/evidence of completion, and a linked competency
- Cross-round rerun-checkpoint logic (weak round -> abbreviated loop -> full loop) is not
  needed yet since only one round type is live

## Acceptance criteria

- A candidate can start a Principal ML Infra / ML System Design round and complete a
  realistic, adaptive 45-60 minute conversation (PRD section 33)
- The round survives a reconnect without losing persisted work
- Interviewer asks materially adaptive follow-ups, not a static question list
- Every reported strength/weakness in the report traces to a persisted evidence ID
- Candidate receives a prioritized improvement plan derived from this round's evidence, not
  generic study advice (PRD section 33)
- Per-session latency and cost are observable (PRD section 27, section 33)

## Open questions

- Exact LLM provider/model for interviewer vs evaluator (PRD section 18 wants provider
  abstraction from day one regardless)
- Whiteboard/canvas artifact - text-only for v0, or minimal diagram upload from the start?

## References

docs/PRD.md sections 5, 7, 8, 9, 10, 12, 21, and section 37 tickets 1, 3, 4, 5, 6, 7, 8, 9,
10, 11, 12.
