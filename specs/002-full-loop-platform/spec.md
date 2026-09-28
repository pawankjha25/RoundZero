# 002 - Full-Loop Platform (P0)

## Status
Draft - backlog only, not yet planned or started. Saved verbatim-in-substance from
`Round_Zero_P0_Implementation_Prompt.docx` (provided 2026-09-01) as the pipeline of work
to pick tasks from next. Nothing in this folder has been scoped into a `plan.md` or
started; see `tasks.md` for the pickable backlog and CLAUDE.md decision 5 ("build one full
vertical slice before widening") for why this is deliberately not being started all at once.

## Why
Spec 001 (ML System Design Vertical Slice) proved the core loop end-to-end for one round
type: setup -> adaptive AI interview -> evidence extraction -> independent evaluation ->
report -> improvement plan, plus history/retry, voice, and a whiteboard workspace on top
(all items in `specs/001-ml-system-design-vertical-slice/tasks.md` are now checked off).

This spec is the next phase: turning that one proven round into a real full-loop
interview *platform* - multi-round interview plans, a hybrid AI/Human/Copilot interviewer
model, an adaptive pressure engine that actively probes for a candidate's level boundary,
evidence-backed evaluation with explicit level-calibration ranges, a hiring-committee-style
full-loop debrief (not a simple average), a real coding workspace and a real system-design
whiteboard wired into the interviewer's context, interview replay, a weakness-to-drill
generator, real-interview experience/outcome capture, and the admin/observability surfaces
all of that needs.

Locked constraint from the source document, carried forward as-is: **do not redesign the
product or reopen locked provider choices** (see "Locked stack" below) unless an existing
implementation constraint requires it. Preserve everything spec 001 already ships; extend,
don't replace.

## Locked technical stack
(As specified in the source document - do not relitigate without an explicit conflict.)

| Layer | Choice |
|---|---|
| Frontend | Next.js + Vercel |
| Backend | FastAPI |
| Database / Auth / Storage | Supabase PostgreSQL |
| Realtime | LiveKit Cloud |
| Voice Agent Runtime | LiveKit Agents |
| STT | Deepgram Nova-3 |
| TTS | Deepgram Aura-2 |
| Live Interviewer | Gemini 2.5 Flash |
| Evidence Extraction | Gemini 2.5 Flash-Lite |
| Evaluation / Report / Debrief | GPT-5 mini |
| Observability | OpenTelemetry |
| Coding UI | Monaco Editor |
| System Design UI | Excalidraw |

Note where spec 001 already diverges slightly from this table (not a conflict to resolve
now, just a fact to know when picking tasks): the live interviewer currently runs on
Gemini 3.6 Flash (2.5 was retired for new API keys, per `tasks.md`'s auth/model notes), and
auth/DB currently run on Supabase Auth + SQLite (`apps/api/db.py`) rather than Supabase
Postgres - moving persistence to Supabase Postgres is in scope for this spec's data-model
work, not yet done.

## Product goal
Round Zero is a full-loop interview simulation and calibration platform. A candidate
creates a target company/role/level/domain interview plan, completes AI and eventually
human interview rounds, receives evidence-backed evaluation, level calibration, a
hiring-committee-style debrief, and targeted practice.

This phase must feel like a serious technical onsite, not a generic chatbot. Quality,
evidence, calibration, replayability, and realistic adaptive probing matter more than
adding many superficial features.

## Scope
In scope: the thirteen P0.x feature areas in `tasks.md`, the common `InterviewRoom`
runtime, the domain-model extensions, the AI pipeline (live + post-round + post-loop),
candidate UX flows, admin/content surfaces, and observability - all listed in `tasks.md`
section by section, matching the source document's sections 3-9.

Out of scope for this spec (explicit non-goals, carried from the source document):
- A full human-interviewer marketplace - only make the architecture/UI/data model
  hybrid-ready (`interviewer_mode = AI | HUMAN | COPILOT`), don't build the marketplace.
- Inventing RZ percentiles or industry benchmarks before real population data exists.
- Self-hosting STT/TTS/LLMs - stay on the locked provider stack.
- Executing arbitrary candidate code inside FastAPI - `CodeExecutionProvider` stays an
  abstraction; P0 may use a mock/safe implementation until a secure sandbox is selected.
- Adding another whiteboard/editor SaaS or API - Excalidraw and Monaco are locked choices.
- Replacing any locked provider in the stack table above.
- Turning the interview UI into a gamified/flashy AI playground.

## Definition of done
(Carried from the source document, for the spec as a whole - individual tasks in
`tasks.md` will each have their own narrower acceptance criteria once planned.)

- Existing working interview flow remains functional throughout.
- A candidate can create a multi-round plan and complete at least conversational,
  system-design, and coding workspace flows.
- The AI interview adapts its probing based on interview state, not only a static script.
- The system-design interviewer receives semantic whiteboard context (not raw mouse
  movements).
- Coding events and the final solution are persisted.
- Round evaluation is independent, rubric-based, and evidence-linked.
- Level calibration can recommend below/at/above target with supporting evidence and
  confidence.
- A completed full loop produces a hiring-committee-style debrief, not a simple average.
- A candidate can replay key interview moments and launch a targeted drill from a
  weakness.
- A candidate can record a real interview experience and later its real outcome, with
  privacy controls.
- OpenTelemetry captures latency/errors/usage/cost-relevant telemetry.
- Lint, typecheck, tests, migrations, and production build all pass.

## Privacy / trust requirements
- Keep provider secrets server-side.
- Real-interview-experience sharing is explicitly opt-in, with Private / Anonymous /
  Community modes.
- Sanitize personally-identifying interviewer information; warn against confidential or
  proprietary disclosures.
- Use calibrated language ("simulation indicates", "interview evidence suggests") - never
  claim an employer would definitely hire or reject.
- Never expose private mentorship/session data to employers or community surfaces.

## Working instructions for whoever picks a task from here
(Carried from the source document's section 14, and consistent with this repo's own
`specs/README.md` convention.)

Before writing code for a picked task: inspect the current repository state (a lot may
have shipped since this spec was written - check `specs/001-ml-system-design-vertical-slice/tasks.md`
and the actual code, not just this document), and produce a concise implementation plan
(a `plan.md` in this folder, or an addition to one) identifying existing files/abstractions
to reuse, schema changes, new interfaces/components, API changes, and test strategy. Then
implement in small vertical slices, running lint/typecheck/tests after each one. Prefer
clean interfaces over microservices (CLAUDE.md decision 1). Do not duplicate existing
abstractions. If a requirement here conflicts with the working repository architecture,
explain the conflict and choose the smallest compatible change rather than a rewrite.
