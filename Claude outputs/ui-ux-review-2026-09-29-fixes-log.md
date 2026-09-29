# UI/UX review (2026-09-29) — code-fix pass log

Source: external review `round-zero-ui-ux-review-2026-09-29.md` (18 findings,
RZ-01–RZ-18). Per your instruction ("when any code issue find - keep fixing
it, design issue we can take later, keep note of all issues"), this pass
investigated each finding against the real code first, then fixed everything
that turned out to be a genuine, verifiable code/functional bug. Everything
below was implemented, `tsc --noEmit` + `eslint` clean, and the backend suite
re-run clean (196 passed, same 3 pre-existing unrelated `test_config_options.py`
failures as before this pass — nothing new broken). **Nothing has been
committed to git** — pending your review/approval per the standing rule.

## Fixed this pass

**RZ-07 — End Round was a single, unconfirmed click.** One misclick ended
and finalized a round with no way back. `components/interview/InterviewHeader.tsx`
now requires a second click ("Continue interview" / "End and evaluate")
before the round actually ends.

**RZ-10 — Compare page hid mismatched round types/levels.** The "vs." heading
was built entirely from the older round's own level/role, so comparing two
rounds of different types or levels silently looked like a same-context
comparison. `app/compare/page.tsx` now states each side's own identity and
shows an explicit warning banner when the two rounds aren't directly
comparable. (Also fixed, found while in this file: a pre-existing
`react-hooks/set-state-in-effect` lint violation unrelated to RZ-10 — a
missing-query-params check was calling `setError` synchronously inside a
`useEffect`; now derived during render instead.)

**RZ-12 — Progress page's trend direction mixed round types.** `buildDiagnosis`
in `app/progress/page.tsx` compared the very first evaluated round ever
against the latest, regardless of round type — a Coding-then-ML-System-Design
candidate could get "trending down" purely from different rubrics, not real
regression. Now scoped to the same round type as the most recent round; if
there's only one round of that type so far, no trend sentence is shown
(no fabricated trend).

**RZ-09 — No "start a new round" CTA for returning users.** `app/dashboard/page.tsx`
only offered a primary CTA via `EmptyState` for brand-new (zero-loop) users;
returning users had only the top nav's "Practice" link. Added a "Start
practice" button in the page header, shown once the user has at least one
loop.

**RZ-03 — Unlabeled `<select>`s and format toggles.** Every `<select>` in
`app/setup/page.tsx` and `app/loops/new/page.tsx` (identical duplicated
`Select` component in both files) rendered a visible `<label>` with no
`htmlFor`/`id` association — clicking the label did nothing, screen readers
announced no name. Fixed via `useId()`. The Text/Voice/Both format button
groups also gained `aria-pressed` + a `role="group"`/`aria-labelledby` wrapper.

**RZ-04 — Feedback sheet, Evidence Drawer, and quota popover were mouse-only.**
None of `components/FeedbackWidget.tsx`, `components/report/EvidenceDrawer.tsx`,
or `components/QuotaPill.tsx`'s popover supported Escape-to-close, moved
focus in on open, or restored focus on close. Added one shared hook
(`lib/hooks/useOverlayDismiss.ts`) used by all three; QuotaPill uses it with
`autoFocus: false` specifically to avoid racing its existing blur-based
auto-dismiss timer.

**RZ-05 — Quota pill/upgrade page didn't distinguish tester grants from the
real free trial.** `cohort` (tester/normal/paid) and `plan` (none/monthly/...)
are independent, but `QuotaPill.tsx` and `/upgrade` both keyed the "Free
trial" label off `plan` alone — a tester (8 rounds, no expiry) was labeled
identically to a real self-signup free user (1 round, 7-day window). Fixed
both to check `cohort === "tester"` explicitly; `/upgrade`'s "None" card now
shows the real entitlement numbers once it's the user's current plan.
Also replaced the 3 literal `&check;` HTML-entity checkmarks on that page
with a real ✓ character (was likely rendering fine via JSX's entity
decoding already, but no reason to keep the ambiguity).

**RZ-01 — Nav had no responsive fallback.** `components/AppShell.tsx`'s nav
(5–6 items) plus account controls (quota pill, profile, sign out, theme
toggle) were one unbreaking flex row with no breakpoint behavior — either
overflowed or squeezed on a narrow viewport. Below `md`, both collapse into
a hamburger-triggered menu (reusing the same `useOverlayDismiss` hook from
RZ-04); `md` and up are unchanged.

**RZ-02 — Empty rounds scored as a genuine 0% / NO HIRE failure (largest fix,
done last on purpose).** A round submitted with zero candidate responses
(abandoned right after starting) went through the same rubric scoring as a
real attempt — every dimension defaulted to NOT_COVERED, producing a
fabricated "0% readiness / NO HIRE," indistinguishable from a real, thorough
failure. Root-caused in `src/roundzero/evaluation/evaluator.py` /
`apps/api/orchestrator.py::submit_round`.

Fix: `submit_round` now checks for at least one real candidate turn *before*
calling the evaluator (or spending an LLM call on nothing) and, if there's
none, builds an explicit `not_assessed` result instead of scoring. New
`not_assessed: bool` field threaded through:
- `roundzero.evaluation.models.ScoredRound` / `RoundEvaluation`
- `apps/api/models.py::EvaluationRecord` (+ migration
  `0008_evaluations_not_assessed.py`, already run against the real dev DB)
- `apps/api/orchestrator.py`: `submit_round`, `_record_to_evaluation`,
  `history_item_out` (readiness_pct/hire_signal now read as `null` for a
  not_assessed round, same as "not evaluated yet" — every existing consumer
  that already filters on `readiness_pct !== null` gets this for free),
  `compare_rounds` (returns "not comparable" same as unevaluated),
  `loop_committee_eligible` (a not_assessed real round blocks committee
  synthesis, same as still-in-progress), `real_interview_prediction` (never
  lets the placeholder 0% win "best round"), `question_progress`.
- `apps/api/routes/report.py`: weakest-dimensions calc now skips a
  not_assessed round when picking "most recent evaluated round".
- Frontend: `lib/api.ts` (`RoundEvaluation.not_assessed`), the report page
  (`app/reports/[roundId]/page.tsx`) now shows an honest "Not assessed - no
  responses were submitted" state instead of the normal score layout, and
  `components/loops/LoopList.tsx` / `app/loops/[id]/page.tsx` show
  "Not assessed - no responses submitted" instead of the generic "Evaluated"
  fallback for these rounds.
- Test fixtures in `tests/unit/test_orchestrator_interviewer_unavailable.py`
  and `tests/unit/test_round_comparison.py` needed one real candidate turn
  added — they were unknowingly relying on the old buggy behavior (scoring
  an empty transcript) to exercise evaluator-failure/comparison logic.

**Bonus (found while verifying, not from the review list):** a pre-existing
`react-hooks/set-state-in-effect` violation in `components/ThemeToggle.tsx`
(the standard next-themes "mounted" hydration-guard pattern, which that
library's own docs recommend verbatim, but this project's stricter eslint
rule flags). Replaced with `useSyncExternalStore` — same visual behavior,
no direct `setState` in an effect body at all.

## Not yet done / needs a decision

I did **not** have reliable notes on the exact content of every one of the
18 original findings after this session's context was compacted partway
through the review triage — rather than guess at specifics I'm not sure of,
here's what I can say confidently:

- **RZ-13, RZ-14** — investigated earlier in this pass and found to be
  *intentional, already-documented* design choices in the code (RZ-14: the
  Hiring Manager round type is deliberately selectable-with-a-warning before
  it's fully available, per an explicit code comment; the admin "Enabled"
  toggle's cosmetic-only nature is also self-disclosed in its own UI copy).
  Not bugs — no code change made.
- **RZ-06** (level defaulting), **RZ-11**, **RZ-15–RZ-18**, and any other
  item not listed as "Fixed" above — these were flagged as design-leaning or
  were still mid-investigation when this session's context got compacted.
  They need a fresh look against the original review doc rather than being
  guessed at here.
- The **full 14-phase live QA dogfooding pass** (Claude in Chrome against
  your running `localhost:3000`, synthetic Staff MLE persona, text-mode
  only, OK to consume 1-2 tester-allowance credits) — not started yet. This
  was explicitly sequenced *after* the review triage per your own answer
  earlier in this session.

## Suggested next step

Point me back at the original `round-zero-ui-ux-review-2026-09-29.md` text
(or I can ask you to re-paste it) so I can finish triaging RZ-06/11/15-18
with the same rigor as the rest, then move on to the live QA pass.
