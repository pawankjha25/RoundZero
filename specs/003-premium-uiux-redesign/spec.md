# 003 - Premium UI/UX Redesign

## Status
Draft - backlog only. Saved verbatim-in-substance from
`Round Zero — Premium UI/UX Redesign & Implementation Prompt.md` (provided 2026-09-01).
Kept as its own spec folder, separate from `specs/002-full-loop-platform/`, at the user's
explicit request - visual/UX work and new backend features are picked and tracked
independently even though many UI items here are blocked on data that spec 002 hasn't
built yet (see "Dependency notes" below).

## Why
The goal is explicitly **not** to redesign backend architecture or replace working
functionality - it's to make the existing product feel like a premium, serious,
trustworthy interview platform: closer to Linear + Stripe + Notion + a premium technical
interview platform than a chatbot, admin dashboard, or gaming app. Every major screen
should answer: what am I preparing for, where am I now, what should I do next.

## Scope
In scope: the 43 numbered sections of the source document - product experience
principle, core UX loop, navigation, dashboard, plan-creation wizard, hybrid-mode UX,
check-in, interview room (flagship), AI interviewer presence, the three workspace types,
end-interview transition, round result, full-loop debrief, hiring committee UX,
evidence-first UX, replay (signature experience), level calibration UX, weakness->drill
UX, real-interview capture/review/outcome, privacy UX, interview journey, interview
intel, empty/loading/error states, visual system, dark mode, motion, responsive strategy,
accessibility, a shared design-system component list, product copy, trust signals, and
analytics events. `tasks.md` breaks each into checkable items, grouped by the source
document's own six-phase implementation priority (section 40).

Out of scope: rewriting working functionality merely to match this document; replacing
real data with mocks (mocks are only acceptable where the backing feature genuinely
doesn't exist yet, per source section 43); anything that isn't a UI/UX/copy/IA change.

## Dependency notes (not in the source doc - added so tasks.md doesn't over-promise)
Several sections describe UI for features spec 002 hasn't built yet - implementing the
*chrome* around them now is fine, but the real experience needs the backend first:
- Full Loop Debrief / Virtual Hiring Committee UX (secs 15-16) needs P0.6.
- Level Calibration / boundary UX (secs 19-20) needs P0.4's calibrated-range data.
- Evidence-First UX / drawers (sec 17) needs P0.5's evidence-ID citations.
- Interview Replay (sec 18) needs P0.9's persisted replay events.
- Weakness -> Drill (sec 21) needs P0.10's drill generator.
- Real Interview capture/review/outcome (secs 22-24) needs P0.11/P0.12.
- Interview Intel (sec 27) needs real aggregate data - start as an IA placeholder only.
- Multi-round loop wizard (sec 5) and Hybrid AI/Human/Copilot round cards (sec 6) need
  P0.1's `InterviewPlan`/multi-round loop and P0.2's `interviewer_mode`.

Everything else (navigation, dashboard reshape around the active target, check-in,
interview room focus mode, the three workspace layouts, visual system/dark
mode/motion/responsive/accessibility, copy, design-system components, empty/loading/error
states) can be implemented against what already exists today.

## Definition of done
(Carried from the source document's section 42, verbatim in substance.)

- Candidate has a clear active target and next action.
- Creating a Round Zero takes only a few intuitive steps.
- AI/Human/Copilot rounds are represented consistently.
- Every round has a professional Check-In.
- Interview Room enters distraction-free Focus Mode.
- Conversational, Coding and System Design rounds share a coherent interview shell.
- Monaco and Excalidraw feel native to Round Zero.
- Connection interruption does not create panic or data-loss ambiguity.
- Evaluation has deliberate processing UX.
- Report begins with a clear conclusion rather than metric overload.
- Level Calibration is prominent and understandable.
- Important evaluator claims can open supporting evidence.
- Evidence can lead directly to Interview Replay.
- Replay synchronizes transcript with available code/whiteboard state.
- Weaknesses lead directly to targeted drills.
- Candidate can log a real interview with minimal friction, and record real outcomes.
- Interview Journey connects simulations, practice and real interviews.
- Empty/loading/error states are polished.
- Desktop and dark mode are excellent.
- Accessibility basics are implemented.
- Existing backend and interview functionality remain intact.
- Lint, typecheck, tests and production build pass.

## Working instructions for whoever picks a task from here
(Carried from the source document's section 43.)

Before implementing: inspect the current frontend and existing design system, list
existing routes/components that can be reused, identify gaps against this spec, and
propose the smallest coherent implementation plan rather than a rewrite. Implement
incrementally, phase by phase (see `tasks.md`), running lint/typecheck/tests/build after
each phase. Keep mock data only where backend functionality genuinely doesn't exist yet,
and never silently replace working real data with mocks. Prioritize product quality over
visual novelty.
