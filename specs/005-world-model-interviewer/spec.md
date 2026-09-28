# 005 - World-model interviewer (forward, inverse, counterfactual)

Source design: "Round Zero: World-Model Interviewer Design and Plan" (Claude Docs,
2026-09-28). This spec is the implementable subset of that doc.

## What and why

Round Zero keeps an explicit, probabilistic **belief about the candidate's level**
per competency, updated after every answer from cited evidence. The same model is
used three ways:

| Direction | Question it answers | Feature |
| --- | --- | --- |
| Forward | "If I ask this, what will I learn?" | Adaptive follow-up picker (ships in **shadow mode**) |
| Inverse | "Given what I saw, what caused the outcome?" | Evidence diagnosis ("where it went wrong") |
| Counterfactual | "If this one answer were different, would the outcome change?" | Flip rewrite (hypothetical, blind re-score) and Retry (real) |

The differentiator vs. generic AI mock interviews: every gap is traced to the exact
answer that caused it, and the candidate sees the smallest change that would have
flipped the outcome, plus a real retry path.

## Competencies (v1, decided 2026-09-28)

Six competencies, each with 4 levels (Below Senior, Senior, Staff, Principal):
problem framing, ML system design, ML depth, trade-offs and judgment, production and
reliability, leadership and influence. Communication is scored inside each, not as
its own axis. They sit **on top of** the existing per-round rubric dimensions: each
round type's dimensions map to a competency in `rubrics/competencies/v1.yaml`.
Existing 1-4 dimension scoring, readiness %, hire signal and reports are unchanged.

## Requirements

1. **Tracking (every turn).** After each candidate answer, extract evidence items
   (dimension, competency, criterion, polarity demonstrated/absent/contradicted,
   verbatim span, strength) and update the belief by Bayes' rule. Evidence spans
   must be verbatim substrings of the answer; items that fail validation are dropped
   (unsupported-claim guard). Adds **no latency** to the interviewer reply.
2. **Level display.** The level estimate is shown **only in the post-interview
   report**, never during the interview (decided 2026-09-28).
3. **Adaptive follow-up.** A picker scores each candidate competency to probe next by
   expected information gain, with constraints (no competency probed more than twice
   in a row, no steering in the last 2 minutes). Modes: `off`, `shadow` (default -
   decision logged, interviewer not steered), `live` (a probe hint is added to the
   interviewer prompt). `live` only after Gate 2.
4. **Diagnosis (inverse).** Per competency: final level + confidence, a path of the
   believed level after each answer, the answer where the level dropped most, and
   ranked causes. A cause's impact is computed exactly: replay the belief without
   that evidence item and measure how much the final level recovers. Abstain when
   evidence is too thin.
5. **Flip rewrite (counterfactual, hypothetical).** For the top gaps, a writer model
   proposes the smallest addition to one answer; an independent scorer (the
   extractor, which does not know it is scoring a rewrite) re-scores the edited
   answer; the belief is replayed with only that answer changed. Always labelled
   hypothetical, never used as training data. Generated on demand, not at submit.
6. **Retry (counterfactual, real).** The candidate can re-answer one question from
   the report; the retry is scored the same way and stored as a real before/after
   pair.
7. **Progress path map (UI).** Report page shows the interview path map per
   competency (one node per answer, confidence band, evidence-coloured nodes, fix
   branch dashed, retry branch solid) and an answer drawer. Progress page shows the
   final level per competency across sessions.
8. **Evaluation.** Simulator (Gate 2), gate metrics (Gate 1), AI pre-labeling agent
   (Pawan reviews), data export + likelihood fitter (Gate 3).

## Non-goals (this spec)

- Training a neural forward model (needs real transcripts first - Gate 3 tooling only).
- A labeling UI (labels are reviewed as JSON files for now).
- Changing the existing evaluator, readiness or hire signal.

## Labeling (decided 2026-09-28)

An AI labeling agent (Anthropic, a different vendor from both the Gemini extractor
and the GPT-5 mini evaluator) pre-labels; Pawan reviews and corrects every episode.
About 20 episodes get an external expert check before any public accuracy claim.
