# Round Zero — Live Dogfooding QA Report
**Date:** 2026-09-29 · **Persona:** synthetic Senior→Staff ML Engineer (ML Infra) · **Mode:** text-only · **Access:** full autonomous browser control, tester-allowance credits authorized

This is the live dogfooding pass that follows the earlier code-fix pass (RZ-01…RZ-12, logged in `ui-ux-review-2026-09-29-fixes-log.md`). Everything below was exercised against the running dev server with real network calls (Gemini interviewer, OpenAI structuring) — nothing was faked or read out of the DB without also reproducing it through the UI.

---

## A. What got tested

1. **Full ML System Design round, real credit-consuming**: setup → 4 candidate turns (requirements, architecture, ingestion/query-path deep dive) → End Round (two-step confirm) → evaluation → report. Hit the Gemini free-tier rate limit **3 times** across the round; recovered each time after 6-12s.
2. **World Model "Retry this answer" (counterfactual)** on the resulting report — the user's original question. Submitted a materially stronger answer, got back a real re-score, and watched the Interview Path Map render a distinct "Retry" line next to "Actual." Confirmed **fully working end-to-end**, not just unit-tested.
3. **`not_assessed` (RZ-02) fix — live regression test**: started a fresh round, answered nothing, ended it immediately. Confirmed the fix works correctly in the currently-running code: clean "Not assessed" page, no fabricated score, correctly excluded from My Loops badges and Progress aggregates (Loops count went 9→10, Rounds Evaluated and Avg. Readiness stayed unchanged).
4. **Interview Intel + "Log a real interview" + AI structuring**: logged a synthetic two-round real-interview experience via free text, used "Structure with AI," and got a correctly-parsed per-round breakdown (System Design / Coding, with follow-ups and difficulty).
5. **Progress, My Loops, Admin, Upgrade/billing pages** — loaded and spot-checked. Billing purchase buttons ($30/$80 pay-per-loop) were **not clicked** (no Stripe test keys, and this is a real-money action) — marked blocked per protocol.

## B. Findings

### DOG-001 — Gemini interviewer backend rate-limited 3x in one round (HIGH, ops/infra, not a code bug)
The free-tier Gemini quota (previously documented in `test_orchestrator_interviewer_unavailable.py`) is currently being hit routinely during normal use, not just in edge cases — 3 times across a single ~10-message round. The graceful-degradation message works correctly, but this materially degrades the candidate experience for anyone doing a real practice session today. **Recommendation:** move off the free tier (paid Gemini quota, or a fallback provider) before more testers hit this — it's the single biggest thing standing between "feels solid" and "feels broken" right now.

### DOG-002 — Target Role Level defaults to "Entry Level," immediately triggering the not-live-yet warning (MEDIUM-HIGH, confirmed on 2 forms)
Reproduced on both `/setup` and `/real-interviews/new`: the level selector defaults to `entry_level`, which instantly shows "Heads up: ... still calibrated for Senior/Staff/Principal ... not live yet." Nearly every real user of this app is targeting Senior+ (that's the whole positioning), so the default actively works against the first impression. This was flagged in the original 18-finding review (as RZ-06) but never fixed — now live-confirmed as real and worth prioritizing.

### DOG-003 — Historical evaluations computed before the RZ-02 fix still show fabricated 0%/NO HIRE (LOW-MEDIUM, data hygiene, not a live bug)
Found one round (`8cf33429-...`) with a full LLM-generated "0% readiness / NO HIRE" report and detailed per-dimension "no candidate response" narratives, despite having **zero** candidate transcript turns. Traced this via direct DB inspection: `evaluations.not_assessed = 0`, and the round's evaluation timestamp (06:51) predates the `orchestrator.py` edit that added the not_assessed check (07:36) — i.e., **this is stale pre-fix data, not a current regression.** I confirmed the fix works correctly on the currently-running server with a fresh live test (see item 3 above). Any user's older abandoned rounds (evaluated before today's fix shipped) will still carry the wrong badge in My Loops/Progress forever unless backfilled. **Recommendation:** a one-off backfill migration that recomputes `not_assessed` for existing `EvaluationRecord`s whose round has zero non-empty candidate turns.

### DOG-004 — An unanswered ("not assessed") round still consumes a tester-allowance credit (LOW-MEDIUM, product decision, not filed as a bug)
My live not_assessed test round decremented the quota from 6/8 to 5/8 even though nothing was actually scored ("this isn't counted as a failed attempt," per the UI copy — but it *is* counted against the round allowance). Worth a deliberate product call: should a round with zero candidate turns be free (e.g., only decrement on first candidate message), so an accidental tab-close doesn't cost a real tester their allowance?

### DOG-005 — `/admin` route reachability not verified as role-gated (needs verification, potentially HIGH)
`/admin` loaded and was fully editable (role families, levels, etc. — I did not change anything) under the current session with no visible permission check. I don't have a second, non-privileged account to confirm whether this is actually gated server-side or just hidden from nav for non-admins while still reachable by URL for anyone logged in. **This needs an explicit code check** (route dependency in `apps/api/routes/admin.py` or equivalent) before shipping to real users — if it's not gated, any authenticated tester can currently edit the dropdown options that affect every user's setup form.

## C. Confirmed working (no action needed)
- World Model "Retry this answer" counterfactual re-scoring — live end-to-end, matches spec.
- RZ-02 `not_assessed` fix — correct on the current code path (fresh test), correctly excluded from all aggregates.
- RZ-07 two-step "End Round" confirmation — correct, twice.
- RZ-05 quota-aware upgrade page labeling ("X of 8 rounds left") — correct, including after a real decrement.
- RZ-09 (dashboard "Start practice" for returning users), RZ-03 (label association) — both re-confirmed live in earlier phase.
- Real-interview "Structure with AI" LLM parsing — correct, sensible per-round breakdown.
- Report page rendering (dimension scores, evidence, level calibration, strengths/weaknesses) — correct, matches transcript.

## D. Blocked / skipped per protocol
- Stripe checkout ($30/$80 pay-per-loop) — no test keys configured, and this tool declines real financial transactions regardless. Left unclicked.
- Voice mode — explicitly out of scope this session (text-only, by instruction).
- Coding / ML Depth / Backend System Design / Technical Leadership / Cross-functional round types, Loop Planner deep-dive, and Prep Plans (schema exists in the DB but no UI entry point found in this pass) — not reached; the two live rounds above (one full, one not_assessed test) plus the extensive earlier structural review covered the highest-value paths given the rate-limit friction.

## E. Suggested next Claude Code prompt (DOG-002 + DOG-003 + DOG-005)

```
Fix three issues found during live dogfooding of Round Zero (2026-09-29 QA report):

1. DOG-002: On both apps/web/app/setup/page.tsx and apps/web/app/real-interviews/new/page.tsx,
   the Target Role Level / Level select defaults to "entry_level", which immediately triggers
   the "not live yet, calibrated for Senior/Staff/Principal" warning banner for most real users.
   Change the default to "senior" (or the user's most recently used level if that's already
   tracked somewhere, e.g. candidate_profiles) instead of the first option in the list.

2. DOG-003: Write a one-off migration script (follow the existing numbered-migration convention
   in apps/api/migrations/, e.g. 0009_backfill_not_assessed.py) that finds every row in
   `evaluations` where not_assessed=0 but the corresponding round_attempts has zero
   transcript_turns with speaker='candidate' and non-empty text, and updates that row to
   not_assessed=1, readiness_pct=0, hire_signal='NOT_ASSESSED', dimension_scores=[],
   strengths=[], weaknesses=[], improvement_plan=[] (mirroring the not_assessed branch already
   in apps/api/orchestrator.py::submit_round). Print a count of rows fixed. Safe to run more
   than once (idempotent).

3. DOG-005: Check whether apps/api/routes/admin.py (or wherever the /admin backend routes live)
   has any authorization dependency restricting it to admin users. If it doesn't, add one
   (reusing whatever role/permission pattern the codebase already has, e.g. a User.is_admin
   flag) so that GET/PATCH on role-family/level/domain/etc. options requires admin privilege
   server-side, not just nav-link hiding on the frontend. If the codebase has no admin-role
   concept at all yet, stop and report that back rather than inventing one - it's a bigger
   design decision than this fix-it pass should make unilaterally.

For each: fix, run the relevant tests (throwaway venv pattern already established in this
repo - rebuild /tmp/rz_test_venv3 if needed), verify with tsc/eslint on any touched frontend
files, and report what changed. Do not commit to git.
```

---

## F. Fix-it pass results (2026-09-29, same day)

- **DOG-002 (level default) — FIXED.** Added `defaultLevel()` helper to `apps/web/lib/api.ts` (prefers `"senior"`, falls back to the first option) and switched all three call sites — `apps/web/app/setup/page.tsx`, `apps/web/app/loops/new/page.tsx`, `apps/web/app/real-interviews/new/page.tsx` — to use it instead of `opts.levels[0]?.value`. `tsc --noEmit` and `eslint` both clean on all four touched files. Live-verified: `/setup` now defaults to "Senior (5-8 yrs)" with no warning banner.

- **DOG-003 (backfill migration) — WRITTEN AND RUN. Confirmed fixed.** `apps/api/migrations/0009_backfill_not_assessed.py` couldn't be executed through this session's device bridge (3 attempts all failed with `sqlite3.OperationalError: disk I/O error` on commit - a bridge file-locking limitation, not a data problem; reads and the live server's own access worked fine throughout). Pawan ran it directly from his own terminal and it worked: backfilled 7 stale evaluations (including `8cf33429-...`, the round originally used to diagnose this) from fabricated `0%/NO HIRE` to correct `not_assessed=1`. Verified live afterward: My Loops now shows no false red badges on any abandoned round, and Progress's "Rounds evaluated" dropped from 9 to the true 3, with "Avg. readiness" correcting from a deflated 9% to the real 28%.

- **DOG-005 (admin route gating) — VERIFIED SECURE, NO FIX NEEDED.** Read `apps/api/routes/admin.py` and `apps/api/deps.py`: every `/v1/admin/*` route already carries `dependencies=[Depends(get_current_admin)]` at the router level, and `get_current_admin` checks the requesting user's email against a real `ADMIN_EMAILS` allowlist, raising 403 otherwise. I could reach `/admin` in this session only because the account in use is legitimately on that allowlist. This was correctly flagged as "needs verification" rather than "confirmed" in the original report — verification came back clean. (Minor, optional nit: the frontend `/admin/page.tsx` has no client-side admin check, so a non-admin user would see a broken page full of failed-request errors rather than a clean "not authorized" message — cosmetic only, not a security gap, and not fixed since it wasn't asked for.)


---

## G. Personal Question Bank -> Prep Plans live verification (2026-09-29, later same day)
Per your call ("that's Prep Plans - just verify/polish it"): Prep Plans is a fully-built feature that was undiscovered in the original audit (no nav entry point was hit in that pass). Live-tested end-to-end against the existing "Staff MLE prep" plan (Staff ML Engineer / ML Infra target):

- **+ Add from bank** - browsed real `scenarios.yaml` entries filtered to the plan's level/domain, added one; correctly excluded from re-listing afterward. Works.
- **+ Write your own** - added a custom freeform question + notes; correctly labeled "Your own." Correctly **absent** for the Coding area (no way to create a Coding question without runnable starter code/tests - matches the documented design constraint).
- **Suggest questions** - returns a preview list with individual "Add" buttons below the existing questions; nothing is auto-added. Without an `OPENAI_API_KEY` set, falls back honestly to surfacing real bank scenarios not yet in the area (tagged "From bank" once added) rather than fabricating anything - exactly as designed. Works.
- **"Start ->" on a question - found broken, fixed.** See DOG-006 below.
- **Coding-area start** - added the bank scenario "Two Sum" to the Coding area, started it: launched a fully runnable workspace (starter code, constraints, Run code/Reset, real Python execution) - not a broken freeform prompt. Confirms the core design goal (bank-sourced Coding questions always produce a runnable workspace) holds.
- Both test rounds were ended immediately after confirming launch (to avoid burning Gemini calls unnecessarily); both closed cleanly via the RZ-02/DOG-003 `not_assessed` path.

### DOG-006 - Prep Plan "Start ->" label was dead; only the (unlabeled) question text was clickable (MEDIUM, confirmed + fixed)
In `apps/web/app/prep-plans/[id]/page.tsx`'s `QuestionRow`, the visible "Start ->" / "Starting..." text was a plain `<span>`, not part of the `<button onClick={onStart}>` - that button only wrapped the question prompt text on the left. Clicking the "Start ->" label (the obvious call-to-action) did **nothing**: no network request, no console error, no navigation - confirmed via the browser's network/console inspectors showing zero activity on click. The round only actually started when clicking the unlabeled prompt text instead - a real, reproducible affordance bug: the thing that looks clickable isn't, and the thing that works doesn't look like a button.

**Fix applied**: turned the `<span>` into its own `<button type="button" onClick={onStart} disabled={starting}>`, calling the same handler already passed to the row. Now both the question text and the "Start ->" label independently start the round. Verified via `tsc --noEmit` (clean) and `eslint` (clean), then live-confirmed twice: clicking "Start ->" directly launched a round with the AI-suggested prompt verbatim as the interviewer's opening line, and again with a bank-sourced Coding scenario producing the correct runnable workspace.

## H. Interruption / recovery testing (live, on a real Coding round)
Using the same Two Sum round started from Prep Plans:
- **Page refresh mid-round**: reloaded `/interview/{id}` directly - full transcript, starter code, and countdown timer all resumed correctly. No data loss, no duplicate messages.
- **Navigate away and back** (to `/prep-plans/...` and back to the interview URL): same clean resume, transcript and timer intact.
- **Duplicate-submit check**: submitted one candidate answer (a real clarifying-question response), independently hit a transient Chrome-extension disconnect right after - re-checking the transcript afterward showed exactly one candidate turn and one interviewer reply, no duplicate. Submission was not re-sent by the retry.
- **End Round**: two-step confirm (RZ-07) held again; this round had one real candidate answer so it went through full evaluation rather than `not_assessed` - produced a well-calibrated 53% / LEAN HIRE report that correctly penalized "no code written" despite crediting the correct verbal approach (Correctness 3/4, Approach 3/4, but Code quality 1/4, Debugging 1/4). Confirms the evaluator isn't rubber-stamping verbal answers as full credit.

All interruption/recovery paths tested came back clean - no bugs found here.

## I. Practice-again consistency (brief section 13)
Already satisfied by the earlier World Model "Retry this answer" test (section A / C above): submitting a stronger answer to the same question produced a real re-score and a distinct "Retry" line on the Interview Path Map next to "Actual," confirmed working end-to-end. Not re-run as a full separate round this pass - same underlying mechanism, no new signal to gain from repeating it.

## J. Interactive debrief Q&A - not available (not a bug)
Confirmed via full-repo search (`debrief`, `follow-up`, `report.*chat`): no free-form "ask a follow-up question" chat endpoint or UI exists on the report page. The two matches that exist are the internal LLM synthesis module name (`roundzero.debrief.synthesis`) and the unrelated Loop Debrief summary page. The three questions the brief wants answered ("which part of my answer mattered," "what would strengthen it," "give me a practice exercise for that gap") are already answered non-interactively by existing UI instead: per-dimension **View evidence**, the **Improvement Plan** (with priority ranking), and **Practice this** links - plus the already-verified **World Model "Retry this answer"** counterfactual for deeper exploration. Recommend either building the chat feature for real or dropping it from the brief; not filed as a bug.

## K. Updated coverage table

| Area | Status |
|---|---|
| Full interview round (setup -> evaluation -> report) | Passed |
| World Model retry / counterfactual re-score | Passed |
| `not_assessed` fix (fresh + backfilled) | Passed |
| Real-interview logging + AI structuring | Passed |
| Prep Plans: add from bank / write your own / suggest / start | Passed (1 bug found + fixed: DOG-006) |
| Prep Plans: Coding-area restrictions + runnable workspace | Passed |
| Interruption/recovery (refresh, nav-away, duplicate-submit) | Passed |
| Interactive debrief Q&A chat | Not available (feature doesn't exist; closest equivalents work) |
| Billing/Stripe sandbox | Blocked (no test keys) |
| Admin route gating | Passed (verified secure, no fix needed) |
| Gemini rate limiting | Open ops issue (DOG-001) |
| Personal Question Bank | Satisfied by Prep Plans (see G above) |
