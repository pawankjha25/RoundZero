# Tasks - 003 Premium UI/UX Redesign

Pickable backlog, grouped by the source document's own six-phase implementation order
(section 40). Check an item only once it's actually implemented and verified (lint +
build + a live look, per this repo's usual convention) - not when merely started. Items
marked **(blocked)** need spec 002 backend work first (see spec.md's "Dependency notes")
and are listed here for completeness, not for picking yet.

## Phase 1 - Design Foundation
- [x] Design tokens: neutral base, one primary brand accent, semantic status colors
      (strong positive/positive/neutral/concern/strong concern) used consistently, never
      color-only (always paired with a label/icon).
- [x] Typography: strong hierarchy, generous line height, monospace only where
      technically appropriate.
- [x] Spacing: generous whitespace outside the interview room, dense-but-controlled
      inside it.
- [x] Navigation: trim primary nav to Home / My Loops / Practice / Progress /
      Interview Intel, then Profile / Settings - move Reports/Evidence/Replay/
      Drills/Questions/Outcomes/Level Calibration into contextual surfaces, not top-level
      nav. Admin stays separate under `/admin`. Correction: the first pass shipped only
      4 of these 5 (dropped My Loops, no dedicated route existed yet) - added back after
      a detailed user IA review made the case for it (see the "My Loops" item below).
- [x] App shell updated to the trimmed navigation. Revised after user feedback: dropped the full-width header border-b (read as a heavy line once --border was darkened for contrast, see CONTRAST_AUDIT.md) in favor of whitespace + a subtle bg-surface/bg-background split, no shadow.
- [ ] Dark mode support throughout (base toggle already shipped in spec 001 - this is
      about extending it to every new/changed surface below, not building it from zero).
- [x] Reusable status/shared components started: `RoundStatusBadge`,
      `InterviewerModeBadge`, `LevelSignal`, `EmptyState`, `AIProcessState`,
      `ConnectionState` (full component list is in spec.md section "Design System
      Components" of the source doc - build incrementally as each is first needed rather
      than all at once).

## Phase 2 - Core Candidate Journey
- [x] Dashboard reshaped around the candidate's primary active target (company / role /
      level / domain / real interview date / days remaining), full-loop progress, a
      restrained current-calibration signal, and one dominant next-action CTA - not a
      grid of equally-weighted analytics cards. Shipped in two passes: first replaced
      the old dashboard with a hero card + an "All loops" list below it; a later user IA
      review pointed out this duplicated what a dedicated loops page should own, so the
      list moved to the new `/loops` page (below) and Home is now just the hero card +
      a "View all your loops" link - closer to a true command center.
- [x] My Loops (`/loops`, new nav item) - full loop/round history + compare mode, moved
      here from Home. Honest caveat: `apps/api/orchestrator.py::create_round` still
      creates a fresh LoopAttempt per round (no multi-round loop code path exists yet -
      P0.1), so every group here is one round today; the page doesn't fake a round-count
      fraction, it's built so the real Loop Planner can slot into the same LoopCards
      later without another IA change. "+ Create Round Zero" CTA per user's branding
      note (was "+ New Interview" in the mockup default, "Start ... " elsewhere).
- [ ] Create Interview Plan: multi-step wizard - Step 1 Target (company/role/level/
      domain/date/optional JD, searchable selectors, popular company cards + Generic/
      Custom), Step 2 Recommended Loop (generated round list the candidate can reorder/
      remove/add/change duration/interviewer mode/difficulty). **(blocked on P0.1's
      multi-round loop + P0.2's interviewer_mode for the full experience - today's Setup
      is single-round/AI-only, so this is a new wizard replacing it, not a restyle.)**
- [ ] Interview Plan detail screen: upcoming/completed rounds, schedule, status, signals,
      preparation.
- [ ] Round cards (`RoundCard`, `InterviewPlanCard`) reusable across dashboard/plan
      detail/journey.
- [ ] Hybrid round representation (AI / Human / Copilot badges + premium human-expert
      card). **(blocked on P0.2's interviewer_mode - design the card now, wire real data
      later.)**
- [ ] Interview Check-In screen before every round: interviewer name, duration,
      difficulty, "you'll need" checklist (mic/environment/workspace-specific item),
      what-to-expect bullets, mic check, Enter Interview CTA.
- [x] Practice landing (`/practice`, new nav destination) - "what to practice" (round-
      type tiles), separate from `/setup` which is now step 2 ("configure this round").
      Per user IA review: My Loops = realistic assessment, Practice = training, and
      Practice shouldn't route straight into Setup. The "recommended for you" drill card
      from the mockup is deliberately left out - needs P0.10's drill generator.
- [x] Progress renamed from `/report` to `/progress` (old URL redirects) - clearer
      against `/reports/[roundId]`, a single round's report, which this page is not.
      Also added a real "Competency trend" - each dimension's actual 1-4 score across
      the candidate's own evaluated rounds, oldest to newest, fetched from existing
      per-round evaluations (no new backend endpoint yet, so this is N report fetches
      client-side - fine at today's history size, worth a real aggregate endpoint if it
      grows). Deliberately NOT shipped: a level-calibration boundary bar (blocked on
      P0.4 - only readiness_pct/hire_signal exist, no calibrated range) and per-skill
      up/down "recent development" arrows (deferred - too few rounds so far for a trend
      arrow to mean anything).

## Phase 3 - Flagship Interview Experience
- [x] Interview Room Focus Mode: remove app navigation/sidebar entirely, minimal header
      (product mark, round type, timer, End Round) - no visible score, competency
      progress, praise, or rubric during the round.
- [x] AI interviewer presence: subtle professional identity (name + role label, no
      cartoon avatar), Ready/Listening/Thinking/Speaking states, subtle voice-state
      animation.
- [x] Conversational workspace layout (ML Depth/Research/Behavioral/Leadership/XFN/
      Hiring Manager round types) - interviewer-forward, transcript accessible but
      visually secondary.
- [ ] System Design workspace layout tuned to ~25-30% interviewer panel / 70-75% canvas
      (Excalidraw integration already exists - this is a layout/chrome pass, not a new
      integration).
- [x] Coding workspace layout polish (Monaco integration already exists) - AI aware of
      meaningful code/run/test events without interrupting typing; checkpoint on
      inactivity/semantic pauses rather than constantly.
- [x] LiveKit connection states + reconnect UX: "Connection interrupted / your interview
      is saved / Reconnecting..." with a Retry Connection action - never lose transcript,
      code, whiteboard, timer, or phase state.

## Phase 4 - Evaluation Experience
- [x] End-Interview transition screen: honest 2-stage checklist (Transcript received /
      Evaluating your interview) via the new AIProcessState-based
      `EndInterviewTransition` - not the source doc's literal 5 stages, since 3 of
      those (evidence extraction as its own step, level calibration, committee packet)
      don't correspond to anything that actually runs yet (no P0.4/P0.6). Also covers
      the failure case (section 30's exact copy: "Your interview was saved
      successfully. Evaluation could not be completed yet." + Retry Evaluation, no
      invented fallback score). Live-verified end-to-end via Chrome: End Round -> real
      ~45s evaluation -> report, zero console errors.
- [x] Round Result information hierarchy: `/reports/[roundId]` rewritten - hero card
      leads with hire-signal badge + readiness % + "the evaluator's view" narrative,
      *then* strengths/weaknesses, dimension detail, improvement plan. (Target level/
      calibrated range/confidence still blocked on P0.4 - only readiness_pct/hire_signal
      exist today, so those aren't shown rather than fabricated.) Also migrated this
      page off the old hardcoded neutral-NNN classes onto the real design tokens - it
      had been missed in the Phase 1-3 pass.
- [x] Evidence Drawer: shell + interaction built and wired to real data
      (`components/report/EvidenceDrawer.tsx`), clicking any dimension opens it. Handles
      both real states honestly: today's live LLMEvaluator path leaves
      DimensionScore.evidence empty, so the drawer says citations aren't available yet
      and falls back to the evaluator's narrative + the full transcript (lazily fetched)
      so the candidate can check it themselves; if evidence[] is ever populated (e.g. the
      RuleBasedEvaluator fallback, or once P0.5 ships for the LLM path) each item is
      already cross-referenced to its transcript turn. No fabricated timestamps (turns
      only carry turn_index) and no "Replay Moment" (blocked on P0.9).
- [ ] Level Calibration section: boundary bar (Senior/Staff/Principal with a confidence
      fill per level), Safe/Competitive/Stretch target labels, calibrated language only
      ("demonstrates Principal-level signals", never "you are a Principal Engineer").
      **(blocked on P0.4 for real calibrated ranges - today's report has a single
      readiness %/hire-signal, not a range.)**
- [ ] Full Loop Debrief tabs: Overview | Rounds | Competencies | Evidence | Level
      Calibration | Improvement Plan - Overview leads with synthesized signal, not a
      simple average. **(blocked on P0.6's committee synthesis + multi-round loops.)**
- [ ] Virtual Hiring Committee panel: Advocate / Skeptic / Level Judge perspectives, each
      claim with a "View Evidence" link; avoid over-anthropomorphizing. **(blocked on
      P0.6.)**

## Phase 5 - Signature Experience
- [ ] Interview Replay timeline: scrubber with strong-signal/weak-signal/missed-
      opportunity/important-decision markers. **(blocked on P0.9's persisted replay
      events - no per-timestamp data exists yet to replay.)**
- [ ] Replay marker detail: synchronized transcript + code state or whiteboard state +
      evaluation annotation for the selected moment. **(blocked on P0.9.)**
- [ ] Weakness -> Drill cards: "observed in N interviews" + Start Drill CTA + drill detail
      card (focus, difficulty, duration, based-on source). **(blocked on P0.10's drill
      generator.)**

## Phase 6 - Real-World Feedback Loop
- [ ] "Log Real Interview" entry point on dashboard/plan surfaces; low-friction capture
      screen (company/role/date + voice-dump or typed free text). **(blocked on P0.11.)**
- [ ] AI-structured experience review screen (per-round question family/follow-ups/
      difficulty, Edit + Save Experience). **(blocked on P0.11.)**
- [ ] Outcome capture screen (Rejected/Advanced/Offer/Withdrew/Waiting, + target vs.
      offered level when an offer). **(blocked on P0.12.)**
- [ ] Privacy picker (Private / Anonymous / Community) with plain-language explanations,
      no dark patterns toward sharing. **(blocked on P0.11/P0.12's storage.)**
- [ ] Rename "History" to "Interview Journey" - unified timeline of simulations, drills,
      real interviews, and outcomes, with filters (Simulation/Practice/Real
      Interview/Offer/Company/Role). Can start now against existing history data even
      before real-interview records exist (just simulations on the timeline at first).
- [ ] Interview Intel information architecture placeholder (typical loop / trending
      topics per company) - build the IA and empty/low-confidence state now; real content
      needs aggregate data this repo doesn't have yet. **(mostly blocked - IA only for
      now.)**

## Cross-cutting (apply throughout every phase above, not a separate phase)
- [ ] Empty states that teach the product (specific copy per surface), never generic
      "No data found."
- [ ] Loading states: skeletons for ordinary loads; staged/explained progress for
      meaningful AI processes (no faked percentages).
- [ ] Error UX: never silently invent a fallback score; evaluation failure shows "saved
      successfully, evaluation could not complete yet" + Retry Evaluation.
- [ ] Motion: subtle only (page transitions, listening/speaking state, evaluation state
      changes, drawers, timeline movement, autosave confirmation) - no bouncing/confetti/
      gradients/gaming effects/constant pulsing.
- [ ] Responsive strategy: desktop-first for the interview room itself (recommend
      laptop/desktop rather than compromising Monaco/Excalidraw on mobile); dashboard/
      reports/progress/journal work well on tablet and mobile.
- [ ] Accessibility: keyboard navigation, visible focus states, ARIA labels, adequate
      contrast, screen-reader-friendly status changes, reduced-motion support,
      non-color-only status indicators, transcript/captions for voice interactions;
      don't let wrappers break Monaco/Excalidraw's own keyboard accessibility.
- [ ] Product copy pass: serious/concise language throughout (e.g. "Start Interview" not
      "Let's crush it!", "Evidence" not "AI Insights", "Level Calibration" not "Your AI
      Career Score", "Simulation indicates" not definitive claims).
- [ ] Trust signals surfaced where appropriate: evaluation confidence, evidence, rubric
      basis, level expectations, model/report version, company-profile confidence,
      Interview Intel source freshness - kept understandable, not overly technical.
- [ ] Analytics events instrumented for the major UX funnel (plan_created,
      plan_started, round_checkin_started, round_started, round_completed,
      round_abandoned, evaluation_viewed, evidence_opened, replay_started,
      replay_marker_opened, drill_started, drill_completed, real_interview_logged,
      real_interview_outcome_added, level_calibration_viewed) - wire into existing
      analytics infra if present, otherwise defer (no infra exists yet as of this
      writing).

## Critical screens to prioritize polish on
(Section 41 of the source doc - once the corresponding phase items above are picked.)
1. Interview Room (Phase 3) - determines whether it feels like a real interview.
2. Full Loop Debrief + Level Calibration (Phase 4) - determines whether users trust it.
3. Interview Replay (Phase 5) - the "this is different" moment.
