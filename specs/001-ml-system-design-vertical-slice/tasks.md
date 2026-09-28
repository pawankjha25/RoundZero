# Tasks - 001 ML System Design Vertical Slice

Phase 1 feature breakdown (E2E MVP #1). P0 = required for the vertical slice to prove the
loop end-to-end. P1 = needed to prove repeat-use value (history/retry) and realism (voice),
landed right after P0. P2 = explicitly deferred past this slice.

## Build milestones (sequencing view - same items above, grouped by shippable checkpoint)

- **M1 - Interview works** (items 1-8): setup -> start interview -> AI interviewer ->
  adaptive follow-ups -> phase state machine -> end interview. Ends at the round's
  `SUBMITTED` state (PRD section 9) - a frozen transcript, nothing scored yet. Deliberately
  the heaviest milestone: interviewer/adaptive-probing quality is the highest-leverage
  thing to get right (see plan.md).
- **M2 - Evaluation works** (items 9-13): transcript -> Evidence Extractor -> Rubric
  Evaluator -> strengths/weaknesses -> level calibration/readiness. Runs entirely off
  frozen M1 transcripts (`SUBMITTED` -> `EVALUATING` -> `EVALUATED`) - buildable and
  iterable without re-running live interviews. Transcripts captured while testing M1 become
  the seed corpus for evals/golden/ml_system_design/.
- **M3 - Product works** (items 2, 3, 12, 14, 15): dashboard -> interview -> report ->
  improvement plan -> history. Where it stops being a pipeline driven by API/script and
  becomes something a candidate actually uses end-to-end and returns to.
- **M4 - Make it feel like a real interview** (item 17): LiveKit -> streaming STT ->
  interviewer agent -> streaming TTS -> natural voice. Only after M1-M3 work in text.

Retry/comparison (item 16) and whiteboard (item 18) aren't in any of the four milestones -
land them as a small increment after M3 and M4 respectively.

## P0 - Core loop (must all land together to call the slice "done")

1. [x] Landing/Login - minimal auth + dashboard. Just enough to identify a candidate
   session; no SSO/password-reset/social login yet.
2. [x] Interview Setup - role, level, domain, optional company, experience
   (FR-001, PRD section 5 step 1).
3. [x] Round Configuration - start an ML System Design round for the configured target
   (single-round LoopPlan; no multi-round Loop Planner logic needed yet).
4. [x] Question Selection - pick/generate an appropriate system-design problem. 10 seed
   scenarios now exist (Definition of Done, .claude/skills/add-interview-round) spanning
   both domains and all three levels; MLSystemDesignInterviewer.pick_scenario() does real
   level+domain filtering with random selection and recent-attempt exclusion (2026-09-01).
5. [x] AI Interviewer - conducts the interactive interview
   (prompts/interviewers/ml_system_design/v1.md).
6. [x] Adaptive Follow-ups - probes based on the candidate's actual answers, not a static
   script (PRD section 8).
7. [x] Timer - 45/60 min with phase awareness (requirements -> architecture -> deep dive ->
   wrap-up); server-authoritative (PRD section 9).
8. [x] Transcript - persist the full interviewer/candidate conversation as append-only
   SessionEvents (PRD section 9).
9. [x] Evidence Extraction - competency-tagged EvidenceItems from the frozen transcript
   (PRD section 10, step 2).
10. [x] Evaluator Agent - independent evaluation after the round completes, never during
    (PRD section 10).
11. [x] Rubric - ML System Design scoring, 1-4 anchored
    (rubrics/ml_system_design/v1.yaml - already seeded).
12. [x] Final Report - scorecard + strengths + weaknesses + evidence
    (PRD section 12, scoped to one round).
13. [x] Readiness - target-level readiness / simulated hire signal, with confidence
    (PRD section 10.1).
14. [x] Improvement Plan - prioritized next steps from this round's evidence
    (PRD section 13).

## P1 - Prove repeat-use value, right after P0 lands

15. [x] Interview History - save completed attempt + report.
16. [x] Retry - GET /v1/rounds/compare (round_id_a, round_id_b) + a dashboard "Compare
    rounds" picker and a /compare page; readiness/hire-signal/per-dimension deltas, always
    ordered older->newer regardless of argument order. Pure arithmetic over persisted
    EvaluationRecord rows, no new LLM call (shipped 2026-09-01).
17. [x] Voice - LiveKit + Deepgram STT/TTS, Text/Voice/Both chosen at Setup time, sharing
    the same orchestrator.post_message() call as text (milestone-4.md's "transport swap,
    not a rewrite") - shipped 2026-09-01. Text fallback stays available.

## P2 - Explicitly deferred

18. [x] Whiteboard - Excalidraw canvas in the System Design split-screen workspace, synced
    into the interviewer's context via workspace_context.

## Sequencing note

Land P0 items roughly in table order - each one is a dependency for what follows it (no
report without evaluation, no evaluation without evidence extraction, no evidence
extraction without a transcript). Do not start P1 until every P0 item is checked.

## Implementation status (hybrid build - real ML System Design slice + mocked shell)

P0 items 1-3 and 5-15 are built and wired end-to-end (apps/web -> apps/api ->
src/roundzero): setup -> interview -> submit -> evaluated report -> history.
One honest gap against the checklist above, not yet closed:

- **Items 9-10 (Evidence Extraction / Evaluator Agent)** - real LLM path now
  wired in: `LLMEvaluator` (src/roundzero/evaluation/evaluator.py) runs GPT-5
  mini as an independent evaluator over the frozen transcript when
  `OPENAI_API_KEY` is set, sharing the same deterministic `compute_readiness()`
  helper as the fallback. Interviewer moved from Claude to `GeminiGateway`
  (Gemini 3.6 Flash, bumped 2026-09 from 2.5 Flash after Google retired it for
  new API keys) behind the same `LLMGateway` interface, per the locked V1
  stack. With no keys set, both still fall back cleanly to
  `RuleBasedEvaluator` / `MockLLMGateway` - no key is required to run the app.
  Report/improvement synthesis (`llm_report_synthesis`) is a second, separate
  OpenAI call, not folded into the evaluator, per the module-separation rule
  in CLAUDE.md/plan.md.

Items 16-18 (Retry/comparison, Voice, Whiteboard) have all since shipped.

## Auth (new item, beyond the original P0/P1 list)

- **Login** (item 1) was originally shipped as a minimal cookie-session auth.
  It has now been replaced end-to-end with **Supabase Auth**: Google OAuth as
  the primary sign-in + passwordless email magic link as the fallback (no
  password field), via `@supabase/ssr` on the frontend and Supabase JWT
  verification (`apps/api/deps.py`) on the backend. Unlike every LLM provider
  above, this has no mock fallback - it needs a real Supabase project
  (`SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY`) and Google configured as an OAuth provider
  before login will work at all.
