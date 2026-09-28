# Round Zero - Product Requirements + Technical Requirements (V1)

**AI-Powered Full-Loop Interview Simulator**

V1 principle: realistic interviewing > generic question bank; evidence > opaque score; improvement > one-time evaluation.

| | |
|---|---|
| Document status | Implementation-ready V1 |
| Primary audience | Founder / engineering team / AI coding agents |
| Product boundary | Standalone Round Zero with clean future Guruvia integration |
| Primary wedge | Senior/Staff/Principal AI/ML engineering interview loops |
| Core promise | Simulate the full interview loop, consolidate evidence, and tell the candidate what to improve next. |

## 1. Executive Summary

Round Zero is an AI-powered full-loop interview simulator. A candidate selects a target role, level, domain, and optionally a company profile. A Loop Planner constructs an appropriate interview loop; specialized interviewer agents conduct realistic, adaptive rounds; independent evaluators score evidence against structured rubrics; a debrief layer consolidates feedback and calibrates readiness; and an Improvement Planner produces a prioritized preparation plan.

V1 is deliberately standalone. It should expose stable APIs/events so that a future Guruvia Career Twin can ingest candidate-approved assessments, strengths, gaps, plans, and longitudinal progress without coupling the first product to the broader mentorship platform.

## 2. Product Goals

- Reproduce the experience of a complete onsite/full-loop interview rather than a single mock round.
- Generate the loop dynamically from role x level x domain x company profile.
- Use specialized interviewer behavior and adaptive follow-up questions.
- Evaluate each round independently before any cross-round aggregation.
- Produce evidence-backed strengths, weaknesses, level/readiness calibration, and a prioritized improvement plan.
- Support repeated loops and show measurable improvement over time.
- Create a technical foundation that can later support B2C candidate preparation and opt-in B2B assessment workflows.

## 3. Non-Goals for V1

- A mentor marketplace or the full Guruvia product.
- Automated hiring decisions for employers.
- Background checks, identity investigation, or employee surveillance.
- Claims that Round Zero reproduces confidential internal company rubrics.
- A full LeetCode-scale problem catalog.
- Perfect anti-cheating/proctoring.
- Mobile-native applications.
- Enterprise ATS integrations in the initial release.
- Real-time collaborative IDE comparable to a commercial cloud IDE.

## 4. Target Users & Initial Wedge

| Persona | Typical target | Primary need | V1 priority |
|---|---|---|---|
| Senior MLE | Staff MLE | Know whether they are ready for the next level | P0 |
| Staff/Principal MLE | Principal / Sr Staff | Full-loop calibration across technical + leadership dimensions | P0 |
| ML Infra engineer | Staff/Principal ML Infra | Coding, distributed systems, ML platform, leadership | P0 |
| Applied/Research engineer | Research Engineer / Applied Scientist | ML depth, research reasoning, coding, system design | P1 |
| General SWE | Senior/Staff SWE | Coding, backend design, leadership | P2 |

## 5. Core User Journey

1. Create candidate profile and choose target role, level, domain, company style, interview date, and desired simulation intensity.
2. Round Zero proposes a loop. Candidate can accept it or customize allowed rounds.
3. Candidate schedules/runs individual rounds or chooses Full Loop mode.
4. Each specialized interviewer conducts an adaptive interview and records structured evidence.
5. After a round, its evaluator submits independent feedback. In Full Loop mode detailed feedback is held until debrief.
6. After sufficient rounds complete, the Evidence Aggregator creates a candidate packet.
7. Debrief/Calibration determines overall readiness, strengths, concerns, and level signal.
8. Improvement Planner generates a prioritized 7/14/21/30-day plan.
9. Candidate practices weak areas and reruns selected rounds or the full loop.
10. Dashboard compares attempts and highlights improvement/regression.

## 6. Loop Planning

The Loop Planner is a deterministic-policy + LLM planning component. It must never freely invent an arbitrary loop without constraints.

### 6.1 Inputs
- Target company profile: generic or configured company archetype.
- Role family: ML Engineer, ML Infra, Research Engineer, Applied Scientist, SWE, Engineering Leader.
- Level: Mid, Senior, Staff, Principal, Sr Principal/Distinguished (configuration-driven).
- Domain: ranking/recommendation, GenAI/LLM, ML infra, CV/multimodal, forecasting, ads, search, AV, general ML.
- Candidate preferences: time available, rounds to exclude, voice/text mode, coding language.
- Optional known interview structure supplied by the candidate.

### 6.2 Output
A versioned LoopPlan object containing ordered/parallelizable rounds, duration, competencies, interviewer persona, rubric version, prerequisites, and debrief weighting rules.

### 6.3 Example: Principal ML Infra loop
See `configs/loops/principal_ml_infra.yaml`.

## 7. Interview Round Requirements

| Round | Duration | Primary competencies | Priority |
|---|---|---|---|
| Coding / DSA | 50 min | Algorithms, correctness, complexity, communication | Core |
| AI-Assisted Coding | 60 min | Decomposition, AI use, verification, debugging, code quality | Configurable |
| ML Algorithm Coding | 50 min | Numerical/ML implementation, vectorization, correctness | Core |
| ML System Design | 60 min | End-to-end ML architecture, scale, reliability, experimentation | Core |
| Backend / Distributed Design | 60 min | APIs, storage, consistency, queues, caching, resilience | Core |
| ML Depth & Breadth | 60 min | Modeling, training, evaluation, inference, trade-offs | Core |
| Research / Experimentation | 50 min | Hypothesis, experiment design, ablation, paper reasoning | Role-dependent |
| Technical Leadership | 50 min | Vision, influence, ambiguity, execution, technical strategy | Core at Staff+ |
| Behavioral | 45 min | Ownership, failure, learning, conflict, impact | Core |
| XFN Collaboration | 45 min | Influence, stakeholder alignment, disagreement, product partnership | Core |
| Hiring Manager | 45 min | Trajectory, scope, motivation, leadership maturity, calibration | Core |

### Coding / DSA
Functional requirements: Executable coding workspace; test cases; complexity discussion; interviewer probes edge cases and trade-offs.
Rubric dimensions: Correctness; algorithm choice; complexity; testing; communication; recovery.

### AI-Assisted Coding
Functional requirements: Candidate can use an approved AI coding assistant panel. System records candidate prompts, accepted/rejected suggestions, edits, tests, and verification behavior.
Rubric dimensions: Problem decomposition; delegation; prompt quality; verification; debugging; code ownership; security awareness.

### ML Algorithm Coding
Functional requirements: Implementation tasks such as loss functions, metrics, attention primitives, sampling, retrieval/ranking utilities, training/evaluation components.
Rubric dimensions: ML correctness; numerical reasoning; vectorization; API quality; tests; complexity.

### ML System Design
Functional requirements: Whiteboard/canvas + conversational interview. Problems should require requirements, data, features/models, training, serving, experimentation, monitoring, reliability and cost.
Rubric dimensions: Framing; ML architecture; data; modeling; serving; scale; reliability; evaluation; cost; trade-offs.

### Backend System Design
Functional requirements: Whiteboard/canvas + conversational interview for distributed services supporting ML/product systems.
Rubric dimensions: Requirements; APIs; data model; storage; consistency; caching; queues/streams; scale; reliability; security; observability.

### ML Depth & Breadth
Functional requirements: Adaptive oral examination driven by declared domain and candidate responses.
Rubric dimensions: Conceptual depth; mathematical intuition; practical trade-offs; failure modes; breadth; ability to reason beyond memorization.

### Research / Experimentation
Functional requirements: Paper/abstract discussion or open research problem; candidate proposes hypotheses, baselines, experiments, ablations and interpretation.
Rubric dimensions: Scientific reasoning; novelty judgment; experimental rigor; statistics; failure analysis; communication.

### Technical Leadership
Functional requirements: Scenario-driven interview around technical direction, large programs, ambiguous decisions, standards and influence.
Rubric dimensions: Scope; strategy; decision quality; influence; execution; mentoring; organizational impact.

### Behavioral
Functional requirements: Evidence-seeking behavioral interview with follow-ups rather than accepting polished STAR stories at face value.
Rubric dimensions: Ownership; learning; conflict; resilience; judgment; self-awareness; measurable impact.

### XFN Collaboration
Functional requirements: Product/engineering/research/design/security conflict scenarios and retrospective examples.
Rubric dimensions: Influence without authority; stakeholder mapping; negotiation; product judgment; conflict resolution; communication.

### Hiring Manager
Functional requirements: Broad synthesis round that tests motivation, trajectory, scope, leadership maturity, role fit and gaps.
Rubric dimensions: Trajectory; level evidence; motivation; scope; leadership; self-awareness; fit.

## 8. Interviewer Agent Behavior

- Interviewer must have a role-specific persona, objective, rubric, time budget, question policy, and prohibited behaviors.
- Do not teach during the interview unless the round configuration explicitly enables coaching mode.
- Ask adaptive follow-ups based on candidate claims, omissions, contradictions, and design choices.
- Maintain realistic pressure without being hostile.
- Use hints sparingly and record every hint because hints affect evaluation.
- Distinguish clarification from coaching.
- Track time and move the interview forward when a candidate over-invests in one area.
- Never expose evaluator chain-of-thought or hidden rubric instructions.
- Generate a structured evidence log: claim, candidate evidence, interviewer probe, outcome, competency tag, timestamp.

## 9. Session State Machine

Canonical states:

`CREATED -> READY -> CHECK_IN -> ACTIVE -> WRAP_UP -> SUBMITTED -> EVALUATING -> EVALUATED`

Exceptional states: PAUSED, DISCONNECTED, ABORTED, EXPIRED, EVALUATION_FAILED. Every transition must be persisted and idempotent.

- Reconnect must restore transcript, timer, coding state, whiteboard snapshot, and current interviewer context.
- Server is authoritative for round state and timing.
- Events are append-only; materialized session state can be rebuilt from event history where practical.
- A completed interview transcript/artifact is immutable; corrections create a new revision.

## 10. Evaluation Architecture

Separate interviewing from evaluation. The interviewer should not be the sole evaluator.

1. Round completes and artifacts are frozen.
2. Evidence Extractor maps transcript/code/whiteboard events to competency-tagged evidence.
3. Primary Evaluator scores the rubric using evidence citations.
4. Optional Critic Evaluator challenges unsupported scores and identifies missing evidence.
5. Score Reconciler produces final per-round ratings and confidence.
6. Only after round-level feedback is committed can the cross-round Evidence Aggregator access it.

### 10.1 Required evaluator output
- Dimension scores using a versioned scale (recommended 1-4 internally; UI may translate to labels).
- Hire signal: Strong No / No / Lean No / Lean Hire / Hire / Strong Hire (configurable).
- Level signal: below target / target / above target with confidence.
- Evidence for every material positive or negative claim.
- Hints received and their impact.
- Critical misses versus optional improvements.
- Evaluator confidence and insufficient-evidence flags.

## 11. Debrief / Virtual Hiring Committee

The debrief is an evidence synthesis process, not a numerical average. It should model conflicting signals, critical competencies, level expectations, and confidence.

- Inputs: immutable round feedback packets only; not raw hidden evaluator reasoning.
- Detect repeated strengths/weaknesses across rounds.
- Apply role/level criticality rules. Example: severe coding weakness may be blocking for an MLE even if leadership is strong.
- Explicitly surface conflicting evidence rather than smoothing it away.
- Produce overall simulated decision, target-level readiness, confidence, top strengths, top risks, and missing evidence.
- Use language such as "Round Zero simulation indicates..." rather than claiming an actual company hiring outcome.

## 12. Candidate Report

- Executive summary and simulated overall signal.
- Round-by-round scorecard.
- Competency heat map.
- Top 3-5 strengths with evidence.
- Top 3-5 weaknesses/risks with evidence.
- Level/readiness calibration and confidence.
- Critical blockers versus nice-to-improve items.
- Representative transcript/code moments.
- Prioritized improvement plan.
- Suggested next practice rounds.
- Comparison with previous attempts when available.

## 13. Improvement Planner

The planner converts evidence into a constrained preparation plan. It must prioritize rather than produce a generic curriculum.

- Inputs: target interview date, available hours/week, round results, competency gaps, candidate preferences.
- Output horizons: 7, 14, 21, or 30 days.
- Each task has objective, expected duration, artifact/evidence of completion, and linked competency.
- Avoid recommending work on already-strong dimensions unless needed for maintenance.
- Recommend rerun checkpoints: weak round first, abbreviated loop next, full loop only when justified.

## 14. Longitudinal Progress

- Store assessment attempts by rubric version.
- Compare only compatible dimensions; show rubric-version warnings where necessary.
- Track trend, not merely latest score.
- Separate improvement due to fewer hints from raw score improvement.
- Show candidate-facing progress timeline and target readiness trend.
- Future Guruvia integration can ingest only candidate-approved derived results.

## 15-16. Functional & Non-Functional Requirements

### Functional requirements (V1)

| ID | Capability | Requirement | Priority |
|---|---|---|---|
| FR-001 | Candidate profile | Create/edit target role, level, domain, coding language, experience summary. | P0 |
| FR-002 | Loop templates | Create versioned generic/company-style loop templates. | P0 |
| FR-003 | Loop planner | Generate a valid LoopPlan from candidate target and policy. | P0 |
| FR-004 | Round execution | Run conversational rounds with timer, transcript and adaptive probes. | P0 |
| FR-005 | Coding workspace | Editor, run/test, stdout/stderr, snapshots, submission artifact. | P0 |
| FR-006 | AI-assisted coding telemetry | Capture assistant interactions and verification behavior. | P1 |
| FR-007 | System-design workspace | Basic diagram/whiteboard artifact upload or embedded canvas. | P1 |
| FR-008 | Voice interview | Real-time audio with transcript and interruption handling. | P0 |
| FR-009 | Independent evaluation | Structured rubric scoring with evidence. | P0 |
| FR-010 | Debrief | Cross-round synthesis and simulated decision. | P0 |
| FR-011 | Candidate report | Web report + exportable artifact. | P0 |
| FR-012 | Improvement plan | Prioritized plan generated from evidence. | P0 |
| FR-013 | Attempt comparison | Compare current and prior loops/rounds. | P1 |
| FR-014 | Admin content | Manage questions, rubrics, personas and company profiles. | P0 |
| FR-015 | Safety/moderation | Report abuse, prompt injection defense, content controls. | P0 |
| FR-016 | Billing/entitlements | Plan/credit enforcement. | P1 |
| FR-017 | Guruvia export boundary | Candidate-controlled export event/API for derived results. | P2 |

### Non-functional requirements

| Area | Requirement |
|---|---|
| Availability | 99.5% V1 service target excluding planned maintenance. |
| Interactive latency | Text interviewer p95 first-token target < 2.5s; voice turn response target should feel conversational, instrument p50/p95. |
| Durability | No loss of completed transcript/code/evaluation artifacts after acknowledgement. |
| Reconnect | Recover active session within 60s without losing persisted artifacts. |
| Security | Encryption in transit/at rest; least privilege; secrets manager; signed artifact URLs. |
| Privacy | Candidate owns assessment data; no enterprise sharing by default; explicit scoped consent for future exports. |
| Auditability | Version every prompt, rubric, model configuration, loop template and evaluator. |
| Observability | Trace every interview turn across STT/LLM/TTS/tool calls with latency, cost and error metadata. |
| Cost controls | Per-session token/audio/code-execution budgets and hard circuit breakers. |
| Accessibility | Keyboard navigation, transcript availability, captions for voice/video where supported. |
| Model portability | LLM provider abstraction for interviewer/evaluator roles; avoid hard-coding one provider. |

## 17. Proposed V1 Architecture

```
Web App
  |
API Gateway / Backend-for-Frontend
  |
  +-- Auth & Candidate Service
  +-- Loop Service ----------------------> Config DB
  +-- Interview Session Service ---------> Event Store / Session DB
  |      |
  |      +-- Realtime Gateway <----------> Voice/STT/TTS Provider
  |      +-- Agent Orchestrator ----------> LLM Gateway
  |      +-- Coding Sandbox
  |      +-- Artifact Store
  |
  +-- Evaluation Service ----------------> LLM Gateway
  +-- Debrief Service -------------------> LLM Gateway
  +-- Improvement Planner ---------------> LLM Gateway
  +-- Report Service
  |
Event Bus / Job Queue
  |
Observability + Cost + Audit Pipeline
```

Future boundary: candidate-approved `AssessmentExport` event -> Guruvia / Career Twin.

> Implementation note (see CLAUDE.md): V1 implements this as a modular monolith - the
> boxes above are module boundaries inside `src/roundzero/`, not separate services, until
> there's a concrete reason to split one out.

## 18. Recommended Technology Stack

| Layer | Recommendation |
|---|---|
| Frontend | Next.js + TypeScript; React; component library; Monaco editor for coding. |
| Backend API | Python FastAPI for product APIs and agent/evaluation services. |
| Realtime voice | LiveKit Cloud for room/media transport; pluggable STT/TTS adapters. |
| Agent orchestration | Custom state-machine/orchestrator first; typed Pydantic contracts. Avoid hiding core interview logic inside a heavy agent framework. |
| LLM gateway | Provider abstraction supporting OpenAI/Anthropic/others; routing by task, cost and latency. |
| Database | PostgreSQL for transactional data/config; JSONB for versioned structured payloads. |
| Cache/session | Redis for ephemeral locks, rate limits and active-session state. |
| Queue | Start with managed Redis queue / cloud task queue; graduate to Kafka only if event volume/use cases justify it. |
| Artifacts | S3/GCS-compatible object storage for transcripts, audio, code snapshots, reports. |
| Coding sandbox | Isolated ephemeral containers/microVM service with CPU/memory/time/network limits. |
| Observability | OpenTelemetry traces + metrics/logs; Grafana-compatible backend. |
| Deployment | Managed container platform initially; Kubernetes only where sandbox/realtime scale warrants it. |

## 19. Core Data Model

| Entity | Key fields / purpose |
|---|---|
| User | id, auth_subject, locale, timezone, created_at |
| CandidateProfile | user_id, experience_summary, domains, preferred_language |
| TargetRole | role_family, level, domain, company_profile_id, interview_date |
| CompanyProfile | name/style, public-source notes, loop policies, version, provenance |
| LoopTemplate | role/level constraints, round definitions, policy version |
| LoopAttempt | candidate, target, loop_plan_version, status, timestamps |
| RoundAttempt | loop_attempt, round_type, interviewer_config_version, status, duration |
| SessionEvent | round_attempt, sequence, event_type, payload, timestamp |
| TranscriptSegment | speaker, text, start/end time, confidence |
| CodeArtifact | language, source, tests, run results, snapshot revision |
| DesignArtifact | canvas/export/upload references, revision |
| Rubric | round_type, dimensions, anchors, criticality, version |
| RoundEvaluation | dimension scores, evidence refs, signal, level, confidence, version |
| DebriefReport | overall signal, readiness, strengths, risks, conflicts, confidence |
| ImprovementPlan | horizon, prioritized tasks, competency links, checkpoints |
| ConsentGrant | subject, recipient/purpose, scope, expiry, revoked_at |
| AssessmentExport | candidate-approved derived payload for future external/Guruvia use |

## 20. API Surface (V1)

| Endpoint | Purpose |
|---|---|
| POST /v1/targets | Create target role/company/level. |
| POST /v1/loops/plan | Generate LoopPlan. |
| POST /v1/loop-attempts | Start a loop attempt. |
| GET /v1/loop-attempts/{id} | Read loop status and rounds. |
| POST /v1/rounds/{id}/check-in | Initialize round and realtime credentials. |
| POST /v1/rounds/{id}/events | Persist client/tool events; idempotency key required. |
| POST /v1/rounds/{id}/submit | Freeze round artifacts. |
| GET /v1/rounds/{id}/status | Round lifecycle status. |
| POST /v1/rounds/{id}/evaluate | Internal/admin trigger; normally async. |
| POST /v1/loop-attempts/{id}/debrief | Internal/admin trigger; normally async. |
| GET /v1/loop-attempts/{id}/report | Candidate-facing consolidated report. |
| POST /v1/loop-attempts/{id}/improvement-plan | Generate/update plan. |
| GET /v1/progress | Longitudinal compatible-attempt trends. |
| POST /v1/exports | Create candidate-approved derived assessment export. |

## 21. Agent Contracts

### 21.1 Interviewer input
```json
{
  "round_type": "...",
  "target_role": {...},
  "interviewer_policy": {...},
  "rubric_summary": {...},
  "time_remaining_sec": 2400,
  "conversation_state": {...},
  "candidate_artifacts": {...}
}
```

### 21.2 Interviewer output
```json
{
  "utterance": "...",
  "action": "ASK|PROBE|CLARIFY|HINT|TRANSITION|WRAP",
  "competency_tags": ["..."],
  "private_state_update": {...},
  "tool_request": null
}
```

### 21.3 Evaluator rule
All evaluator conclusions must reference persisted evidence IDs. Reject/flag any material score or claim without evidence.

## 22. Prompt & Configuration Management

- No prompts embedded directly in route handlers.
- Every agent prompt has name, semantic version, owner, purpose, model constraints and test set.
- Rubrics are configuration, not prose hidden inside prompts.
- Store model/provider/temperature/tool configuration with every attempt.
- Support shadow evaluation of a new evaluator version against historical anonymized test cases before promotion.
- Company-specific content must record provenance and avoid representing unofficial/public information as confidential employer policy.

## 23. Coding Sandbox Requirements

- Ephemeral isolated execution environment per candidate/round.
- Disable outbound network by default.
- Strict CPU, memory, process, filesystem and execution-time limits.
- Supported V1 languages: Python first; Java/C++ can follow.
- Run candidate code against visible and hidden tests.
- Persist source snapshots and execution metadata, not the entire container.
- AI-assisted coding round must separately log assistant suggestions and candidate verification/actions.
- Never execute untrusted code in the application/API container.

## 24. Voice / Realtime Requirements

- Candidate can complete conversational rounds by voice; text fallback always available.
- Streaming STT with partial/final transcripts.
- Interviewer should support interruption/barge-in.
- TTS must be cancellable when candidate starts speaking.
- Persist final transcript separately from raw audio.
- Audio retention should be configurable; candidate should know whether audio is retained.
- Realtime degradation should fail gracefully to text instead of losing the interview.

## 25. Privacy, Trust & Data Boundaries

- Round Zero candidate data is private by default.
- No assessment is shared with an employer, Guru, or Guruvia without an explicit scoped action/consent.
- Future enterprise sharing uses a derived Talent/Assessment Passport, never private mentorship notes.
- Consent must identify recipient/purpose/scope and support revocation where applicable.
- Do not use private candidate interview content to train externally shared models without explicit permission.
- Provide deletion/export controls consistent with applicable product/legal requirements.
- Separate private development feedback from any future employer-facing assessment product.

## 26. Safety & Integrity

- Treat candidate text/code as untrusted input; defend system prompts and tools from prompt injection.
- Tool permissions are round-specific and least-privilege.
- Never reveal hidden evaluation instructions or other users' content.
- Use bounded tool schemas rather than arbitrary shell/tool access for interviewer agents.
- Detect evaluation failures and route to retry/manual review rather than fabricating scores.
- Do not claim guaranteed interview outcomes.

## 27. Observability & Product Analytics

- Per-turn latency: STT, orchestration, LLM TTFT/total, TTS, client playback.
- Per-round cost: tokens, audio minutes, sandbox compute, storage.
- Drop/disconnect/reconnect rates.
- Round completion and full-loop completion rates.
- Evaluator retry/failure/disagreement rates.
- Candidate report view rate and improvement-plan completion.
- Repeat-round rate and longitudinal improvement.
- Conversion: signup -> planned loop -> first round -> completed loop -> paid repeat usage.

## 28. Quality & Evaluation Harness

Round Zero itself needs an evaluation system before public release.

- Golden interview transcripts with expert-labeled competency evidence and expected score bands.
- Interviewer tests: relevance, follow-up quality, hint leakage, repetition, difficulty calibration, time management.
- Evaluator tests: evidence grounding, score stability, false-positive/false-negative weaknesses, level calibration.
- Adversarial tests: prompt injection, candidate attempts to obtain rubric, nonsensical answers, overconfident bluffing.
- Regression suite for every prompt/rubric/model change.
- Human review panel for a sample of sessions; measure agreement between expert and AI evaluation.
- Do not optimize only for score agreement; separately evaluate usefulness of feedback and realism of interview behavior.

## 29. Admin / Content Operations

- CRUD/versioning for role profiles, loop templates, interviewer personas, question families and rubrics.
- Question tagging by domain, difficulty, competency and freshness.
- Disable/retire leaked, low-quality or overused questions.
- Preview/test interview persona before publishing.
- Review evaluator disagreements and failed sessions.
- Feature flags for new round types/models.

## 30. Repository Structure (original PRD sketch)

> Superseded in this repo by CLAUDE.md's `src/` layout + modular-monolith decision - kept
> here for reference to the original document.

```
roundzero/
+-- apps/
|   +-- web/                    # Next.js candidate/admin UI
|   +-- api/                    # FastAPI BFF/public API
+-- services/
|   +-- orchestrator/           # session state + interviewer control
|   +-- evaluator/              # evidence extraction + round scoring
|   +-- debrief/                # cross-round synthesis
|   +-- planner/                # loop + improvement planning
|   +-- realtime/               # LiveKit/STT/TTS adapters
|   +-- sandbox/                # isolated code execution interface
+-- packages/
|   +-- contracts/              # Pydantic/JSON schemas
|   +-- prompts/                # versioned prompt assets
|   +-- rubrics/                # versioned competency rubrics
|   +-- configs/                # role/company/loop configs
|   +-- llm_gateway/
|   +-- observability/
+-- evals/
|   +-- golden/
|   +-- interviewer/
|   +-- evaluator/
|   +-- adversarial/
+-- infra/
+-- migrations/
+-- tests/
+-- docs/
```

## 31-32. MVP Build Sequence & Scope Cut

For the first usable private beta, do NOT implement all eleven rounds. Build the architecture for all, but ship five high-signal rounds:

1. Coding / DSA
2. ML System Design
3. ML Depth & Breadth
4. Technical Leadership / Behavioral
5. Hiring Manager

Then add ML Algorithm Coding, Backend Design, XFN, AI-Assisted Coding, Research, and specialized company loops as configuration/content maturity improves.

| Milestone | Deliverable | Indicative solo build |
|---|---|---|
| M0 - Skeleton | Repo, auth, Postgres, contracts, LLM gateway, telemetry. | 2-3 days |
| M1 - Text interview | One ML System Design round, state machine, transcript, adaptive interviewer. | 3-5 days |
| M2 - Evaluation | Evidence extraction, rubric evaluator, candidate round report. | 3-5 days |
| M3 - Coding | Python Monaco workspace + isolated runner + coding evaluator. | 4-7 days |
| M4 - Full loop | Loop Planner + 5 core round types + async evaluations + consolidated debrief. | 7-10 days |
| M5 - Voice | Realtime audio/STT/TTS, interruption, reconnect/fallback. | 4-7 days |
| M6 - Improvement | Improvement planner + attempt comparison + dashboard. | 3-5 days |
| M7 - Hardening | Eval harness, admin config, privacy controls, billing/limits, production QA. | 5-10 days |

> This repo's build order follows `specs/` instead - see
> `specs/001-ml-system-design-vertical-slice` for the first slice, which corresponds to
> M0-M2 above.

## 33. Acceptance Criteria for Private Beta

- A candidate can create a Staff/Principal ML target and receive a valid loop.
- At least five round types can run end-to-end.
- A 45-60 minute round survives reconnect without losing persisted work.
- Interviewer asks materially adaptive follow-ups rather than a static list.
- Every reported strength/weakness can be traced to evidence.
- Full-loop debrief can represent conflicting round signals.
- Candidate receives a prioritized improvement plan rather than generic study advice.
- Second attempt can be compared with first on compatible rubric dimensions.
- Per-session cost and latency are observable.
- No candidate data is shared externally by default.

## 34. Success Metrics

- >=70% of users who start a paid/private-beta full loop complete enough rounds to receive a debrief.
- >=60% rate the simulation realism 4/5 or better.
- >=70% rate the consolidated feedback 4/5 or better.
- Expert review finds >=80% of material feedback claims evidence-supported.
- >=30% of completed-loop users return for at least one targeted re-assessment within 30 days.
- Median candidate can identify their top 3 preparation priorities after reading the report.
- Unit economics tracked from day one; establish target gross margin after real model/audio usage is observed.

## 35. V1 -> Guruvia Integration Contract

Round Zero remains independently useful. Future Guruvia integration should occur through a candidate-controlled derived event, not direct database coupling.

```json
AssessmentExport {
  candidate_id,
  target_role,
  assessment_date,
  competency_summary[],
  strengths[],
  development_areas[],
  readiness_band,
  improvement_plan_summary,
  provenance: {
    loop_attempt_id,
    rubric_versions[],
    evaluator_versions[]
  },
  consent_grant_id
}
```

Do not export raw private transcripts, hidden evaluator reasoning, or future mentorship notes by default.

## 36. Future Roadmap (Not V1)

- Company-specific loop packs with carefully maintained provenance.
- Research Scientist and Applied Scientist deep loops.
- Promotion Board / Promotion Committee simulator.
- Architecture Review / Design Arena.
- Leadership Lab and XFN conflict simulations.
- Executive communication and presentation simulator.
- Guru review workflow: candidate chooses to share a Round Zero report with a human Guru.
- Talent Passport and candidate-controlled enterprise pipeline.
- Enterprise-configured assessment loops and ATS integrations.
- Benchmarking based on sufficiently large, privacy-preserving cohorts.
- Multimodal whiteboard/video analysis where it materially improves evaluation.

## 37. First Engineering Tickets

1. Define Pydantic contracts: TargetRole, LoopPlan, RoundDefinition, SessionEvent, Rubric, EvidenceItem, RoundEvaluation, DebriefReport.
2. Create PostgreSQL schema + Alembic migrations for users, targets, loop attempts, rounds, events, evaluations.
3. Implement LLMGateway interface and one provider adapter.
4. Implement versioned prompt/config loader.
5. Implement interview session state machine with idempotent event append.
6. Implement ML System Design interviewer V0.
7. Create ML System Design rubric V0 with anchored 1-4 scoring.
8. Implement evidence extractor and evaluator V0.
9. Build minimal Next.js interview UI with text conversation and timer.
10. Build report page for one completed round.
11. Create 10 golden ML System Design transcript fixtures and expert expected outcomes.
12. Add OpenTelemetry trace IDs across API -> orchestrator -> LLM -> evaluator.
13. Add per-attempt token/cost accounting.
14. Only after the above works: add voice and coding sandbox.

## 38. Key Product Decisions to Preserve

- Round Zero is a full-loop simulator, not a question bank.
- Interviewing and evaluation are separate concerns.
- Debrief is evidence synthesis, not score averaging.
- Role/level/company configuration drives the loop.
- Longitudinal improvement matters more than a single readiness number.
- Candidate data is private by default.
- Guruvia integration is opt-in and derived-data based.
- Start with a narrow ML/AI wedge; architect for broader roles later.
- Build realism and evaluation quality before adding a large catalog of rounds.

## Appendix A - Suggested 1-4 Rubric Anchors

| Score | Meaning | Anchor |
|---|---|---|
| 1 | Below bar | Major gaps; cannot complete the competency without substantial guidance. |
| 2 | Mixed / developing | Partial success; important omissions or repeated hints; not consistently at target level. |
| 3 | Meets bar | Competent, independent performance at the target level with reasonable trade-off reasoning. |
| 4 | Exceeds bar | Deep, efficient, high-judgment performance; anticipates issues and demonstrates scope above target. |

## Appendix B - Example Evidence Item

```json
{
  "id": "ev_123",
  "round_id": "rnd_ml_design_01",
  "competency": "reliability",
  "polarity": "negative",
  "source": "transcript",
  "source_ref": "segment_184",
  "observation": "Candidate proposed a single-region serving tier and did not address regional failure until prompted.",
  "hint_level": 1,
  "confidence": 0.94
}
```

## Appendix C - Definition of Done for an Interview Round

- Versioned interviewer persona and rubric exist.
- At least 10 representative question/scenario seeds exist.
- Adaptive follow-up policy is defined.
- Artifacts/tools required by the round are implemented.
- Golden evaluation cases exist.
- Evidence extraction supports the round.
- Evaluator passes regression thresholds.
- Candidate report renders round-specific feedback.
- Latency/cost telemetry is available.
- Failure/reconnect paths are tested.

---

*Source: `Round_Zero_V1_PRD_Technical_Requirements.docx`, imported into this repo on 2026-08-31.*
