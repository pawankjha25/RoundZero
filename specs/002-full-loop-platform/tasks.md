# Tasks - 002 Full-Loop Platform (P0)

Pickable backlog, saved from `Round_Zero_P0_Implementation_Prompt.docx` (2026-09-01).
Checking an item here means "picked and planned" (a `plan.md` exists or is being
written), not "shipped"; only check the box once it's actually done, mirroring
`specs/001-ml-system-design-vertical-slice/tasks.md`'s convention. Cross-references to
spec 001 note where a building block already exists so a picked task doesn't get
re-built from scratch.

P0.1 and (most of) P0.6 have since shipped (2026-09-03) - this file's own "nothing
started yet" framing had gone stale by the time that work landed; see each section
below for what's actually done. P0.13 turned out to already be effectively done too
(verified, not built, 2026-09-03) - most of what it asks for was a side effect of
building the report/progress pages for spec 001's one live round type early on, and
already generalized cleanly once more round types existed.

## P0.1 - Interview Plan + Loop Configuration (shipped 2026-09-03)
- [x] `InterviewPlan`-equivalent: `LoopAttempt` + `PlannedRound` (`apps/api/models.py`) -
      a loop is created with a name, one shared target company/role/level/domain, and one
      or more planned rounds up front (`apps/web/app/loops/new/page.tsx`, POST
      `/v1/loops` -> `orchestrator.create_loop`). No separate per-round schedule/date
      field beyond duration - not part of what shipped.
- [x] Each planned round: type, duration, status (via its started `RoundAttempt` once
      begun), modality. No difficulty or interviewer-mode field yet - those are P0.2/P0.3.
- [x] Support round types: every type in `RoundTypeIcon.tsx`/`ROUND_TYPES` is selectable
      into a loop (`PlannedRound.round_type` isn't restricted at creation). Only
      `ml_system_design`, `coding`, and `ml_depth` have a real interviewer
      (`orchestrator.REAL_ROUND_TYPES`) and can actually be started
      (`start_planned_round`) - the rest sit in the loop honestly labeled "not available
      yet" (`PlannedRoundOut.startable`), same pattern the old /loop-planner preview used.
- [x] Company -> Role -> Level -> Domain -> Loop config data-driven/versionable - the
      option tables were already admin-editable; `LoopAttempt`/`PlannedRound` are the
      real multi-round Loop layer on top (superseding the old "1 round per loop" note
      this file used to carry here).

## P0.2 - Hybrid Interviewer Model
- [ ] Add `interviewer_mode = AI | HUMAN | COPILOT` to the round/config data model.
- [ ] AI mode fully implemented first; data model/UI/scheduling/evaluation schema/APIs
      must not need a redesign to add HUMAN later.
- [ ] Human rounds eventually use the same structured rubric/evidence system.
- [ ] COPILOT: human leads, AI observes and tracks evidence/coverage, can suggest probes.

## P0.3 - Adaptive Interview / Pressure Engine
- [ ] Interview state (not a static question list) driving difficulty adaptation.
      (`MLSystemDesignInterviewer` already does adaptive follow-ups per spec 001 item 6 -
      this item is about generalizing/deepening that into an explicit pressure engine.)
- [ ] Pressure dimensions: depth, ambiguity, scale, failure modes, constraints, cost,
      pushback, tradeoffs.
- [ ] Escalate when the candidate is performing strongly; probe downward to find the
      candidate's stable performance boundary.
- [ ] Never expose internal scoring during the live interview.

## P0.4 - Level Calibration + Level Boundary Detection
- [ ] Evaluate against the target level AND adjacent levels.
- [ ] Output a calibrated range (e.g. Strong Senior -> Staff).
- [ ] Evidence-based wording ("demonstrates Principal-level signals"), never a flat claim.
- [ ] Report Safe Target / Competitive Target / Stretch Target where confidence permits.
- [ ] Base calibration on explicit level-expectation definitions, not free-form LLM
      opinion.

## P0.5 - Evidence-Backed Evaluation
- [ ] Keep interviewer/evaluator separation (already true - CLAUDE.md decision 4).
- [ ] Every competency score/concern/strength/level signal cites evidence IDs tied to
      transcript segments, code events, whiteboard state, or other observable behavior.
- [ ] Evidence extractor runs post-interview, produces structured evidence; GPT-5 mini
      evaluates from the evidence packet + rubric.
      (Evidence extraction + `LLMEvaluator` already exist for the one live round type -
      see `src/roundzero/evaluation/evaluator.py` - this item is about the explicit
      evidence-ID-citation contract, not building evaluation from zero.)
- [ ] Anchored rubric scoring with confidence; avoid unsupported precision.

## P0.6 - Virtual Hiring Committee (shipped 2026-09-03, one deliberate scope cut)
- [x] Full-loop result is a synthesis, not a simple average, once 2+ real rounds in the
      loop are evaluated (`orchestrator.loop_committee_eligible`/`generate_committee_report`,
      `src/roundzero/debrief/committee.py`, GET/POST `/v1/loops/{id}/committee`). Overall
      readiness/hire-signal/confidence stay deterministic (never LLM-judged, same
      "evaluator scores, LLM only writes prose" split evaluation/evaluator.py already
      uses); only the qualitative synthesis is a real GPT-5 mini call
      (`prompts/committee/v1.md`), with a rule-based no-key fallback.
- [x] Advocate / Skeptic / Level Judge perspectives - one combined prompt/call
      (`prompts/committee/v1.md`), not separate services, per this item's own framing.
- [x] Skeptic explicitly challenges unsupported positive conclusions - verified live:
      a strong System Design round's "multi-region failover" strength was paired with a
      Skeptic-flavored concern that it never addressed data-consistency tradeoffs.
- [x] Committee output: overall signal, strengths, concerns, confidence, key evidence -
      done. **Not done, on purpose:** a calibrated level *range* (e.g. "Strong Senior ->
      Staff") - that needs real level-expectation data (P0.4), which doesn't exist yet;
      inventing a range without it would be exactly the fabricated-precision P0.13
      already warns against. Ships instead as a plain directional `level_signal`
      ("trending at/above/below the stated target level, based on X and Y"). Revisit once
      P0.4 lands.

## P0.7 - Coding Workspace
- [ ] Monaco Editor: language selector, problem statement, constraints, editor, Run Code,
      tests/output, reset, autosave, final submission.
      (`CodingWorkspace.tsx` and `src/roundzero/coding/execution.py`/`feedback.py`
      already exist per the repo's file layout - verify current state before rebuilding;
      likely partially done already.)
- [ ] Persist candidate code and meaningful coding events: edits/checkpoints, run
      attempts, test outcomes, errors, final solution.
- [ ] `CodeExecutionProvider` abstraction; never execute arbitrary candidate code
      directly in FastAPI. Mock/safe implementation is fine until a secure sandbox is
      chosen. (Matches this repo's own `MockCodeExecutionProvider` convention used
      elsewhere - "never fabricate a result".)

## P0.8 - System Design Whiteboard
- [ ] Excalidraw for ML System Design and Backend System Design rounds.
      (`SystemDesignWorkspace.tsx` + `apps/web/lib/workspace/summarizeScene.ts` already
      exist - spec 001 item 18 shipped an Excalidraw whiteboard synced via
      `workspace_context`. Verify it already satisfies this item before re-scoping it.)
- [ ] Drawing operations, autosave, reconnect/restore, persistence.
- [ ] Never send raw mouse movements to Gemini - debounce and transform scene state into
      compact semantic context: components, labels, connections, major updates.
- [ ] Feed semantic representation into interviewer state for architecture-aware
      questions.

## P0.9 - Interview Replay
- [ ] Persist timestamped replay data: transcript/audio references, interviewer turns,
      code events, test runs, whiteboard snapshots/deltas, phase changes, evaluation
      evidence.
- [ ] Replay UI with timeline markers: strengths, concerns, missed opportunities, key
      evidence.
- [ ] System design: reconstruct canvas near the selected timestamp.
- [ ] Coding: show code state near the selected timestamp.
- [ ] OK to start with transcript + code/canvas timeline before full synced audio replay.

## P0.10 - Weakness -> Drill Generator
- [ ] Convert detected weaknesses into targeted short practice rounds (e.g. 15-min
      failure-handling system-design drill, 12-min influence-without-authority drill).
- [ ] Each drill specifies: source weakness/evidence, target competency, difficulty,
      duration, success criteria.
- [ ] Support Assess -> Diagnose -> Practice -> Reassess as a product loop.

## P0.11 - Real Interview Experience Capture
- [ ] Let candidates record a real interview experience after interviewing at a company.
- [ ] Capture: company, role, level, team/domain if known, date, loop structure, round
      types, question families, follow-ups, difficulty, notes, self-assessment.
- [ ] Support typed input and a low-friction free-form/voice-dump flow that AI structures
      afterward.
- [ ] Focus on question families/patterns; do not encourage disclosure of confidential or
      proprietary information, interviewer identities, or prohibited material.

## P0.12 - Real Interview Outcome Capture
- [ ] Track actual outcome: rejected, moved forward, offer, withdrew, no response; stage;
      target level; offered/downleveled level when voluntarily provided.
- [ ] Link outcome to prior Round Zero simulations where possible.
- [ ] Store simulation prediction vs. real-world outcome so future calibration can be
      measured.
- [ ] Privacy choices: Private, Anonymous Contribution, Community/Sanitized Sharing.

## P0.13 - Readiness / Progress Foundation (verified 2026-09-03: mostly already shipped)
- [x] Longitudinal **competency** history across sessions - `EvaluationRecord` keeps one
      permanent row per evaluated round (`dimension_scores`, never overwritten), already
      generalized across every real round type, not just one (`apps/web/app/progress/page.tsx`
      groups by `round_type` generically). **Level-calibration** history is explicitly NOT
      done - there's no level-calibration output anywhere yet to have a history of; blocked
      on P0.4 landing first, same dependency P0.6's level-range cut already documented.
- [x] Data needed for future Interview DNA / readiness trajectory / RZ Score / candidate
      passport is already being retained, not computed-and-discarded: every `EvaluationRecord`
      and `LoopCommitteeRecord` persists indefinitely, and `GET /v1/report` already returns
      `total_loops`/`total_rounds`/`evaluated_rounds`/`avg_readiness_pct`/`latest_readiness_pct`
      - a real trajectory summary, not a fabricated score (`apps/api/routes/report.py`).
- [x] Meaningful personal progress from the candidate's own prior sessions, generalized
      across round types/loops - done (`/progress`'s per-dimension trend + stat tiles).
      Two things page's own comments flag as deliberately NOT built: a level-calibration
      boundary bar (blocked on P0.4, not this item's job) and up/down trend arrows per
      skill (skipped on purpose - too few rounds so far for a 2-point arrow to mean
      anything without reading as false statistical confidence).

## Cross-cutting (span multiple P0.x items above - track once, referenced by many)
- [ ] Common `InterviewRoom` shell: header/timer/round metadata, `AIInterviewerPanel` +
      voice controls, `WorkspaceRouter` -> Conversational | Coding | SystemDesign
      workspace, interview state machine/phase tracking, autosave/reconnect, End
      Interview flow. (Conversational + SystemDesign + Coding workspace routing already
      exists per `WorkspaceRouter.tsx`/`InterviewRoom.tsx` - confirm it already matches
      this shape before rebuilding.)
- [ ] Domain model additions: `InterviewPlan`, `InterviewRound`, `InterviewerMode`,
      `RoundConfiguration`, `InterviewSession`, `InterviewPhase`, `CandidateEvent`,
      `TranscriptSegment`, `CodeEvent`, `CanvasEvent`/`Snapshot`, `Evidence`,
      `Competency`, `Rubric`, `LevelExpectation`, `RoundEvaluation`, `LevelCalibration`,
      `CommitteeDebrief`, `DrillPlan`, `RealInterviewExperience`,
      `RealInterviewOutcome`. Extend existing types, don't create parallel ones.
- [ ] Keep all prompts/rubrics/company/role/level definitions/interviewer
      personas/loop templates/level expectations versioned/config-driven
      (CLAUDE.md decision 2 - already the house rule, just needs extending to the new
      config types above as they're built).
- [ ] AI pipeline: live (Deepgram Nova-3 -> pressure engine -> Gemini 2.5 Flash ->
      Deepgram Aura-2) with compact live context (current question, phase, recent turns,
      compressed summary, covered/uncovered competencies, important claims, level probes,
      semantic code/canvas context - never resend the full transcript every turn);
      post-round (transcript + events -> Gemini 2.5 Flash-Lite evidence extraction ->
      GPT-5 mini independent evaluation); post-loop (round evaluations -> GPT-5 mini
      virtual hiring committee/debrief). All claims traceable to evidence.
- [ ] Candidate UX: Create Plan -> configure target/rounds -> choose AI/Human/Copilot
      where supported -> schedule -> review; Full Loop mode hides intermediate feedback
      until debrief, Practice mode shows immediate feedback; Plan detail
      (upcoming/completed rounds, schedule, status, signals, preparation); Round report
      (evidence-backed strengths/concerns, competency scores, level signals, replay,
      targeted drills); Full Loop Debrief tabs (Overview | Rounds | Competencies |
      Evidence | Level Calibration | Improvement Plan); Real Interview capture + later
      outcome capture.
- [ ] Admin/content surfaces: companies, roles, levels, domains, loop templates, round
      templates (role/level/domain/company already admin-editable - loop/round templates
      are new); question/scenario bank with topic/level/difficulty/follow-ups/
      provenance-confidence/status/version; competencies/rubrics/anchored
      scores/level expectations; interviewer personas/prompt versions/model config;
      sessions/evaluations with privacy-conscious access; real-interview-intelligence
      records with moderation/sanitization controls; operational metrics (model calls,
      latency, failures, token/voice usage, estimated cost per round).
- [ ] Observability: instrument end-to-end round latency, STT/LLM/TTS latency,
      errors/retries, token usage, audio minutes, estimated variable cost; log
      prompt/config/rubric/model versions for reproducibility; eval fixtures for
      interview quality, follow-up relevance, evidence extraction, rubric consistency,
      level calibration, committee synthesis; never silently convert a failed evaluation
      into a successful-looking report.

## Suggested implementation order
(Carried from the source document's section 11 - a suggestion for whoever plans this
next, not a commitment.)

1. Inspect repo; map existing plan/room/Gemini flow/models/APIs/tests against this list.
2. Extend domain/data model for workspace type, interviewer mode, evidence, level
   calibration, replay events, real-interview records.
3. Stabilize common `InterviewRoom` + state machine.
4. Adaptive Pressure Engine + evidence-aware interviewer context.
5. `SystemDesignWorkspace` with Excalidraw semantic context (largely done - verify).
6. `CodingWorkspace` with Monaco + `CodeExecutionProvider` abstraction (largely done -
   verify).
7. Post-round evidence extraction + independent evaluation + level calibration.
8. Full-loop Virtual Hiring Committee.
9. Replay foundation/UI.
10. Weakness -> Drill generation.
11. Real Interview Experience + Outcome capture.
12. Admin/config surfaces + observability/evals.
