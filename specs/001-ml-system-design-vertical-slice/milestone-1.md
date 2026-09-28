# Milestone 1 - Interview Works

## Status
Built (text-only, MockLLMGateway - no ANTHROPIC_API_KEY set yet). Runs
end-to-end: apps/web/app/setup -> apps/web/app/interview/[roundId] -> SUBMITTED.
Swap in AnthropicGateway by setting ANTHROPIC_API_KEY - apps/api/orchestrator.py
already picks it automatically over the mock, no code change needed.

## Scope
Setup -> Start Interview -> AI interviewer -> Adaptive follow-ups -> 45-minute phase state
machine -> End Interview. Corresponds to tasks.md items 1-8. Ends at the round's
`SUBMITTED` state (PRD section 9) - a frozen transcript, nothing scored yet. Evaluation
(Evidence Extractor, Rubric Evaluator, level calibration) is Milestone 2 and runs entirely
off the transcript this milestone produces.

## Runtime flow

1. Candidate logs in (minimal auth) and lands on a bare setup page - no dashboard/history
   yet, that's Milestone 3.
2. Candidate fills the setup form (role, level, domain, company, duration) and hits Start.
   Backend creates a CandidateProfile if none exists, a TargetRole, and a trivial
   single-round LoopAttempt wrapping one RoundAttempt for ML System Design (see Decision 1
   below) - no real Loop Planner logic.
3. Check-in picks a scenario from the seeded question bank, loads the interviewer prompt
   and rubric versions onto the round, round moves CREATED -> READY -> CHECK_IN -> ACTIVE.
   State machine starts at phase INTRO, timer starts, coverage map initializes to
   NOT_COVERED across all ten rubric dimensions.
4. Turn loop: candidate message in -> orchestrator assembles the interviewer's input
   (round type, phase, time remaining, coverage map, transcript so far, rubric *summary*
   only - never the scoring anchors, per PRD section 8's "never expose hidden rubric
   instructions") -> LLM Gateway call -> interviewer returns an utterance, an action
   (ASK/PROBE/CLARIFY/HINT/TRANSITION/WRAP), competency tags, and an updated
   coverage/phase state -> appended as an immutable SessionEvent -> utterance sent back to
   the candidate.
5. Server holds the clock. The interviewer should self-transition phases as time/coverage
   dictate, but there is a hard server-side cutoff to WRAP_UP regardless of what the
   interviewer decides (PRD section 9: server is authoritative for round state and timing).
6. Candidate (or the timer) ends it -> WRAP_UP -> submit -> transcript freezes -> round
   moves to SUBMITTED. Milestone 1 stops exactly there.

## Build checklist (dependency order)

Foundation (nothing else works without these):
- Pydantic contracts - TargetRole, RoundAttempt, SessionEvent, interviewer input/output
  shapes (PRD section 21.1/21.2) - src/roundzero/domain/
- SQLite schema (Postgres-ready via DATABASE_URL, apps/api/db.py) for User, LoopAttempt,
  RoundAttempt, TranscriptTurn, EvaluationRecord - apps/api/models.py. Simplified vs. a
  fully general CandidateProfile/SessionEvent event-sourced model - see
  apps/api/models.py's own docstring for why, and what promoting either would look like.
- LLMGateway interface + one real provider adapter - src/roundzero/llm/
- Versioned prompt/config loader (reads prompts/interviewers/ml_system_design/v1.md by
  name + version, never a hardcoded string) - src/roundzero/llm/ or domain/
- Session state machine with idempotent event append
  (CREATED -> READY -> CHECK_IN -> ACTIVE -> WRAP_UP -> SUBMITTED) - src/roundzero/interview/

Round-specific:
- ML System Design interviewer V0 - src/roundzero/interviewers/ml_system_design/agent.py -
  implements the phase state machine + adaptive probing against the prompt file (needs
  real content written - prompts/interviewers/ml_system_design/v1.md is still a TBD
  placeholder)
- At least one real scenario seed to test against (e.g. the multi-tenant ML inference
  platform example) - prompts/interviewers/ml_system_design/scenarios.yaml, versioned like
  the prompt itself

API surface (Milestone 1 subset of PRD section 20):
- POST /v1/loop-attempts (creates the trivial single-round wrapper + its RoundAttempt)
- POST /v1/rounds/{id}/check-in
- POST /v1/rounds/{id}/events
- POST /v1/rounds/{id}/submit
- GET /v1/rounds/{id}/status

Frontend (apps/web):
- Minimal login page
- Setup form
- Interview conversation page (chat + timer; keep a phase indicator visible at least for
  debugging)
- End Interview action

## Decisions

1. **LoopAttempt wrapper.** Resolved: yes. Milestone 1 creates a trivial single-round
   LoopAttempt under the hood even though real Loop Planner logic is skipped. Near-zero
   extra cost now, avoids a schema migration later - PRD section 20's report/progress
   endpoints are keyed off loop-attempts/{id}, not round IDs.
2. **Reconnect.** Resolved: minimal reconnect is in Milestone 1 scope. A reload re-fetches
   transcript + phase state from the event log. Full graceful mid-stream reconnect
   (voice/websocket-level) is deferred to Milestone 4, alongside voice itself.
