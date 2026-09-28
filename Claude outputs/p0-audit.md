# P0 Master Prompt vs. actual repo state

## TL;DR

More is already built than the uploaded prompt assumes. Two full round types (ML System Design, Coding) work end-to-end with real Monaco/Excalidraw workspaces, real voice (LiveKit + Deepgram), independent evaluation, and evidence-backed reports — none of that needs to be built from scratch. The real gaps are concentrated in exactly the three things the prompt itself calls the product's differentiators: the Adaptive Pressure Engine is only partially there, Level Boundary Detection doesn't exist yet, and the Virtual Hiring Committee doesn't exist yet — today a "loop signal" is a plain average of per-round scores, which is the one thing section 24 explicitly says not to do. That's also, conveniently, your own repo's own internal audit already agrees with mine: `specs/002-full-loop-platform/tasks.md` is a near-identical breakdown of this same source prompt, saved 2026-09-01, with per-item notes on what already exists — I cross-checked it against the real code rather than trusting its (now slightly stale) checkboxes.

## Method

I read every relevant file directly — `apps/api/models.py`, `orchestrator.py`, all routes, `schemas.py`, the `src/roundzero/` package, `apps/web/components` and `app/`, `package.json`, `configs/`, `prompts/`, `rubrics/`, `evals/`, and the repo's own `specs/001` and `specs/002` folders (which turned out to already contain a prior pass at this exact audit). Where the prompt claims something exists, I confirmed it by reading the actual implementation, not just a filename.

## Feature matrix (numbered to match the uploaded prompt)

**§3 Target Profile — Partial.** Company/Role/Level/Domain are real, admin-editable, DB-backed option tables (`CompanyProfileOption`, `RoleFamilyOption`, `LevelOption`, `DomainOption`) — genuinely config-driven, not hardcoded. Missing: no `real_interview_date` or `job_description` field anywhere in the schema — those two specific inputs from the prompt aren't captured today.

**§4 Full Loop Planner — Partial.** One real config-driven loop template exists (`configs/loops/principal_ml_infra.yaml`) plus the `LoopAttempt`/`PlannedRound` data model to hold a recommended multi-round loop. Only one template exists though — the "Company × Role × Level × Domain → recommended loop" matching logic isn't a general engine yet, it's one seeded example.

**§5 Custom Loop Builder — Done.** `/loops/new` supports adding/reordering rounds, per-round duration (admin-configurable `DurationOption`s), scheduled vs. unscheduled rounds ("Not started" vs. "Not available yet" states), all real.

**§6 Future-proof interviewer mode — Missing.** No `interviewer_mode`/`agent_config_id`/`human_interviewer_id` fields exist on `RoundAttempt`. Every round is implicitly AI-only at the schema level, so adding Human/Copilot later would need a real migration, not just a config flip.

**§7 Specialized AI interviewers — Partial.** The `INTERVIEWERS` registry pattern in `orchestrator.py` is architecturally exactly what the prompt asks for (config-driven, easy to extend), but only 2 of the 11 listed round types have a real interviewer built: ML System Design and Coding. The other 9 (ML Coding, Backend System Design, ML Depth, Research, Technical Leadership, Behavioral, XFN, Hiring Manager, AI-Assisted Coding) show as "Coming soon" everywhere.

**§8 Interview Check-In — Unconfirmed/likely partial.** I didn't find a dedicated pre-round Check-In screen (mic/LiveKit/audio checks, "Enter Interview" CTA) as its own step between Setup and the interview room — Setup collects config and appears to go straight in. Worth a closer look before assuming this exists.

**§9 Focus Mode Interview Room — Done.** `InterviewHeader.tsx` matches the spec almost exactly: R0 branding, round name, timer, connection state, End Round — no score/evaluator feedback leaked during the round.

**§10 Voice Interview — Done.** Real LiveKit + Deepgram Nova-3/Aura-2 pipeline (`src/roundzero/realtime/agent.py`, `tokens.py`, `VoiceControls.tsx`), Text/Voice/Both chosen at Setup, shares the same `orchestrator.post_message()` as text. Per the repo's own tasks.md this shipped 2026-09-01.

**§11 Interview State Engine — Partial.** A real compact `ConversationState` exists (phase, coverage, turns) rather than resending full transcripts — but it doesn't yet carry compressed summaries, candidate claims, pressure history, or level probes, since those concepts don't exist yet either (see §12/§13).

**§12 Adaptive Pressure Engine — Partial.** The interviewer genuinely adapts follow-ups to what the candidate says (real, not scripted) — but there's no explicit multi-dimension pressure model (scale/failure/cost/pushback/etc.), no escalation tracking, and no persisted `PressureEvent`s. It's adaptive in spirit, not yet the structured engine the prompt describes.

**§13 Level Boundary Detection — Missing.** No `LevelProbe` concept, no "test above/below target level" logic, no calibrated range output anywhere in the evaluator or report.

**§14 Coding Workspace — Done.** Real Monaco Editor (`@monaco-editor/react`, dark-mode synced), problem/constraints/editor/tests/output/run/reset, persisted via `/workspace/code` and `/workspace/run`, a real `CodeExecutionProvider` abstraction behind a mock/safe execution backend (never runs candidate code directly in FastAPI, exactly as specified).

**§15 System Design Workspace — Done.** Real Excalidraw canvas, autosave/restore via `/workspace/canvas`, and `lib/workspace/summarizeScene.ts` genuinely extracts a semantic architecture summary (components/connections) rather than sending raw mouse events — feeds into `workspace_context` the interviewer actually reads.

**§16 Conversational Workspace — Partial.** `ConversationalWorkspace.tsx` exists and is routed to correctly, but since only 2 of 11 round types have a real interviewer, it's mostly unused today — it'll matter once more specialized interviewers (§7) ship.

**§17 Evidence Capture Engine — Partial.** Real `EvidenceItem` extraction (dimension, text, source_turn_index) feeds the evaluator today. Narrower than the prompt's schema though: no persisted `evidence_id` addressable via the API, no `confidence` field, and no `source_type` beyond transcript — code/canvas events are captured but not yet wired into evidence extraction.

**§18 Independent Evaluator — Done.** Real separation maintained (`CLAUDE.md` decision 4, enforced in code): `LLMEvaluator` runs GPT-5 mini independently, never the interviewer grading itself.

**§19 Rubric System — Done.** Versioned YAML rubrics (`rubrics/coding/v1.yaml`, `rubrics/ml_system_design/v1.yaml`), anchored 1–4 scoring exactly as specified.

**§20 Evidence-backed scoring — Mostly done.** Every dimension score carries an `evidence_narrative` plus a real evidence list, and the report UI has a working "View evidence →" drawer — functionally the "Why?" the prompt asks for, even without formal evidence-ID citation syntax.

**§21 Round Signal — Mostly done.** Real 5-tier hire signal (STRONG HIRE → NO HIRE) driven by `readiness_pct`. Missing: no separate `confidence` value distinct from the percentage itself.

**§22 Level Calibration — Missing.** No calibrated range, no Safe/Competitive/Stretch target output — today's report gives a flat readiness % and hire signal only.

**§23 Competency Map — Done.** Real dimension-by-dimension scores rendered per round.

**§24 Virtual Hiring Committee — Missing, and worth flagging specifically.** `components/loops/LoopList.tsx`'s `loopAggregate()` computes a loop's overall signal as a plain average of each evaluated round's `readiness_pct`. Section 24 of your own prompt explicitly says "Do NOT average scores" — this is the one place current behavior actively contradicts the spec, not just falls short of it.

**§25 Full Loop Debrief — Missing.** No Overview/Rounds/Competencies/Evidence/Level Calibration/Improvement Plan tabbed view exists — loop-level "result" is just the averaged badge above.

**§26 Practice Mode — Partial.** `/practice` exists and correctly separates Practice from Full Loop, but only ML System Design is enabled there — Coding already has a real interviewer (built this week) but isn't wired into Practice yet, which looks like a quick win.

**§27 Question/Scenario Library — Partial.** Real versioned YAML scenario files exist per round type (`prompts/interviewers/*/scenarios.yaml`) — genuinely config-driven — but there's no admin CRUD surface for it (no Draft/Published/Retired workflow, no difficulty/provenance/status fields, no UI). Admin today manages options/durations/round-types/study-resources/settings, not a question bank.

**§28–31 Real Interview Journal, Question Capture, Outcome Capture, Privacy Controls — Missing.** `/intel` explicitly says "Interview Intel is built from candidates logging real interview experiences... that capture flow is coming soon" — confirmed nowhere else in the codebase does this exist yet.

**§32 Basic Progress — Done** for what currently exists: `/progress` shows real loops/rounds-evaluated counts, average readiness, and a genuine per-dimension competency trend across actual rounds — no fabricated percentiles, matches the spec's explicit ban on those.

**§33 Home Experience — Partial.** Dashboard shows Upcoming/Finished loops clearly, which answers "where am I now" — but it's not built around one dominant active target with one dominant next-action CTA the way the prompt describes; it currently shows a list of loops rather than "Google — Staff ML Engineer — Sep 28 — Start ML System Design."

**§34 My Loops — Done.** `/loops` exists with the right structure; the primary CTA is currently labeled "Create Loop" rather than "+ Create Round Zero" — a copy difference, not a functional gap.

**§35 Interview Intel (P0 foundation) — Done**, and matches the spec closely: real nav item, honest "not enough reports yet" empty state, explicitly no fake community stats.

**§36 Admin Interview Studio — Partial.** Real admin surfaces exist for role families/levels/domains/companies/durations/round-types/study-resources/settings — a solid chunk of "Interview Catalog." Missing entirely: Question Bank/Scenarios, Competencies/Rubrics/Level Expectations admin UI, AI Config (personas/prompt versions/model config), Operations (sessions/evaluations/costs), Intelligence (real interview contributions) — none of those admin sections exist yet.

**§37 Configuration Versioning — Partial.** Prompts/rubrics genuinely are versioned (`v1` files, `prompt_version` threaded through evaluator/synthesis calls) — but I didn't confirm the specific version used gets persisted on each completed round for reproducibility later. Worth verifying before relying on it.

**§38 Observability — Missing.** No OpenTelemetry instrumentation anywhere in your own code (Next.js ships it internally, unused by you). No latency/error/token/cost telemetry being captured today.

**§39 Evaluation Harness — Partial.** A real golden-fixture eval suite exists (`evals/golden/ml_system_design/`, 9 fixtures, real `test_golden.py`) — genuinely first-class, not an afterthought, matching `CLAUDE.md` decision 3. But it only covers ML System Design; Coding has no golden evals yet, and none of the harder dimensions (pressure escalation, hint leakage, committee synthesis) are covered because those systems don't exist yet either.

**§40 Failure/Recovery — Done** for what's checkable in code: the report page already shows the exact "Your interview was saved, evaluation could not be completed yet, Retry Evaluation" pattern the spec asks for (I built that button this session), and `ConnectionState.tsx` handles a reconnect/retry UI. Live network-drop behavior wasn't tested end-to-end today.

**§41 Security — Partial/spot-checked only.** Route handlers consistently scope data to the owning user (`_get_owned_round` pattern), which is the right shape. I didn't do a full audit of every secret/env boundary today — worth a dedicated pass before this matters in production.

**§43 Explicitly excluded from P0 — Correctly absent.** No human marketplace, no RZ Score, no percentiles, no Candidate Passport, no recruiter portal — none of the things the prompt says not to build were built. Good discipline.

## What to take next

Your own repo already agrees with this prioritization — `specs/002-full-loop-platform/spec.md` calls the pressure engine, level calibration, and hiring committee "major differentiators," and section 52 of the uploaded prompt names the same three as the protected golden-path chain. They're also the highest-leverage gaps because the data they'd consume (dimension scores, evidence, multiple round evaluations per loop) already exists — this is composition on top of what's built, not new plumbing.

1. **Virtual Hiring Committee (§24).** Replace `loopAggregate()`'s naive average with a real synthesis pass once a loop's required rounds are evaluated — Advocate/Skeptic/Level Judge as one orchestrated GPT-5 mini call, extending `debrief/synthesis.py` rather than writing a new module. This is the one place current behavior directly contradicts the spec, so it's worth leading with.
2. **Level Calibration (§22).** Add a calibrated range (Safe/Competitive/Stretch) to the evaluator output — builds directly on the `dimension_scores` that already exist per round.
3. **Full Loop Debrief page (§25).** The UI to surface #1's output — Overview/Rounds/Competencies/Evidence/Level Calibration/Improvement Plan tabs.
4. **Adaptive Pressure Engine, formalized (§12).** Turn the already-working adaptive follow-up behavior into explicit tracked pressure dimensions/events — start with `ml_system_design` since it's the most mature interviewer.
5. **Then, once the core chain is real:** Real Interview Journal + Outcome Capture (§28–31) and a real Question/Scenario admin library (§27) — both are currently "coming soon" placeholders with no functional path yet, and both are more self-contained additions than the four above.

One housekeeping note: `specs/002-full-loop-platform/tasks.md` still says "nothing started" as of 2026-09-01, but the coding round type, voice, and the Excalidraw workspace have all shipped since — worth updating its status so the next person (or session) doesn't re-audit from scratch the way I just did.
