# Milestone 3 - Product Works

## Status
Built: real dashboard history, setup form, and report screen wired to the real
backend (apps/web/app/dashboard, /reports/[roundId]). Retry/comparison (tasks.md
item 16) not started.

## Scope
Dashboard -> Interview -> Report -> Improvement Plan -> History. Corresponds to tasks.md
items 2, 3, 12, 14, 15 (12 overlapping with Milestone 2 - see note below). This is where
the pipeline built in Milestones 1-2 stops being something driven by API calls and becomes
a product a candidate logs into, uses end-to-end, and returns to.

Note on the overlap with Milestone 2: Milestone 2 produces the *data* for the final report
(RoundEvaluation, readiness, Primary Concern) as an API response. Milestone 3 builds the
actual page that renders it the way the report mockup shows - scorecard,
strengths/weaknesses lists, evidence text, primary concern callout.

## Runtime flow

1. Candidate logs in, lands on a real dashboard - list of past attempts (empty state on
   first visit), "Start New Interview" action. Replaces Milestone 1's bare setup-only
   landing page.
2. Setup + interview + evaluation proceed exactly as built in Milestones 1-2, just reachable
   from the dashboard shell instead of standalone.
3. Candidate lands on the polished Report page once the round reaches EVALUATED.
4. After viewing the report, candidate is asked for prep constraints - hours/week
   available, target interview date (see Decision 1) - and the Improvement Plan is
   generated from this round's evidence at the chosen horizon (7/14/21/30 days, PRD
   section 13).
5. The completed attempt (transcript, evaluation, report, plan) persists and appears on the
   dashboard's history list on the candidate's next visit.

## Build checklist (dependency order)

- Dashboard page (apps/web) - lists the candidate's LoopAttempts; a flat list is enough,
  full Longitudinal Progress trend logic (PRD section 14) is out of scope for this slice
- Report page (apps/web) - consumes the GET /v1/loop-attempts/{id}/report data Milestone 2
  already produces; this milestone is the UI layer over it, not new computation
- Prep-constraints form (hours/week, target date) shown after the report, not in the
  original setup form (see Decision 1)
- Improvement Planner - src/roundzero/improvement/planner.py, prioritizer.py
  (see Decision 2 for the scoring approach)
- API: POST /v1/loop-attempts/{id}/improvement-plan
- History list endpoint (e.g. GET /v1/candidates/{id}/loop-attempts) + dashboard UI -
  mostly "free" since the trivial LoopAttempt rows already exist from Milestone 1's
  Decision 1

## Decisions

1. **Where to collect hours-available / target-interview-date.** PRD section 13 needs both
   as Improvement Planner inputs, but Milestone 1's setup form (Target Role/Level/Domain/
   Company/Interview/Duration) never collects them. Recommend: ask in a short follow-up
   form after the report is shown, not upfront in setup - a candidate who hasn't seen their
   result yet doesn't know if they need a plan, and it keeps the original setup form as
   simple as the wireframe intended.
2. **Improvement Planner logic.** Recommend: rule-based task selection for V0, consistent
   with the "deterministic core, narrow LLM use" pattern already set in Milestone 2 - rank
   competency gaps by score ascending and rubric weight descending (worst and most heavily
   weighted first), generate one task per gap up to what fits the chosen horizon. Task
   objective text can be short LLM-generated copy per gap; which gaps get picked and in
   what order stays deterministic, not model-decided.
