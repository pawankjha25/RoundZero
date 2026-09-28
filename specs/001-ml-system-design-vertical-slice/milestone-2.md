# Milestone 2 - Evaluation Works

## Status
Built, with a documented deviation: RuleBasedEvaluator
(src/roundzero/evaluation/evaluator.py) scores off the interviewer's coverage
map rather than an LLM-based Evidence Extractor + Evaluator, since only
MockLLMGateway is wired in today. Same Evaluator interface either way - see
tasks.md's "Implementation status" section and the module's own docstring.

## Scope
Transcript -> Evidence Extractor -> Rubric Evaluator -> strengths/weaknesses -> level
calibration/readiness. Corresponds to tasks.md items 9-13. Starts from a Milestone 1
output: a SUBMITTED RoundAttempt with a frozen transcript. Produces a persisted
RoundEvaluation - the underlying data and computed report content (scorecard,
strengths/weaknesses, evidence narratives, readiness %, hire signal, Primary Concern
headline). Rendering that as a polished candidate-facing page is Milestone 3's job -
Milestone 2 can ship as a raw JSON API and still be "done."

## Runtime flow

1. Round moves SUBMITTED -> EVALUATING once triggered (see Decision 2 on sync vs async).
2. Evidence Extractor reads the frozen transcript + SessionEvents and produces a list of
   EvidenceItems (PRD Appendix B format): competency tag, polarity, source_ref pointing to
   a specific transcript segment, confidence.
3. Primary Evaluator loads rubrics/ml_system_design/v1.yaml (ten weighted dimensions, 1-4
   anchors) and scores each dimension using only the extracted evidence - never inventing
   beyond what's evidenced. Each dimension gets a score, an evidence narrative synthesized
   from that dimension's EvidenceItems (per plan.md's evidence_format), and an
   insufficient-evidence flag where warranted.
4. Level Calibration computes readiness % and hire signal (e.g. LEAN HIRE) deterministically
   from the weighted scores plus level-criticality rules - never asked of the model
   directly, per plan.md.
5. Primary Concern headline is generated (see Decision 4 below).
6. Round -> EVALUATED, RoundEvaluation persisted.

## Build checklist (dependency order)

- src/roundzero/evaluation/evidence_extractor.py
- src/roundzero/evaluation/evaluator.py - rubric-driven, evidence-cited scoring
- src/roundzero/evaluation/level_calibrator.py - deterministic readiness %/hire signal
- EvidenceItem and RoundEvaluation contracts - src/roundzero/domain/ (data shapes);
  evaluation/ holds the logic that produces/consumes them, not a second copy of the schema
- API: POST /v1/rounds/{id}/evaluate (trigger), GET /v1/rounds/{id}/status (now also
  reports EVALUATING/EVALUATED), a data endpoint for the computed report content (can be
  the real GET /v1/loop-attempts/{id}/report from day one, even before Milestone 3 builds
  a page for it)
- evals/golden/ml_system_design/ - real content, not just the README. Use transcripts
  captured while testing Milestone 1 as the first golden fixtures + expert-expected
  outcomes (PRD ticket 11). Per .claude/skills/add-interview-round's Definition of Done,
  Milestone 2 is not actually done without at least a handful of these checked in.

## Decisions

1. **Coverage-map trust.** The interviewer's own coverage map (plan.md's phase state
   machine) is a hint for the Extractor/Evaluator, not ground truth - they must
   independently re-derive what was actually covered from the transcript itself, never take
   the interviewer's self-report at face value. Otherwise the interviewer is effectively
   grading itself by claiming coverage it didn't earn, which breaks the PRD's core
   separation-of-concerns principle (section 10).
2. **Sync vs async evaluation.** Recommend: call the evaluation pipeline synchronously
   in-request for V0. PRD section 20 marks POST /v1/rounds/{id}/evaluate as "normally
   async," but a real job queue is infrastructure this milestone doesn't need yet - add it
   later if/when synchronous LLM-eval latency actually becomes a UX problem, not
   preemptively.
3. **Critic Evaluator.** Recommend: out of Milestone 2. PRD section 10 describes a
   four-stage pipeline (Extractor -> Primary Evaluator -> Critic -> Reconciler); collapsing
   to two stages (Extractor -> Evaluator) for V0 is fewer moving parts to prove the core
   loop works, with strict evidence-citation enforced via prompt/schema validation instead
   of a second adversarial LLM pass. Add the Critic once evals/adversarial/ exists to
   actually measure whether it improves anything, rather than adding it on faith.
4. **Primary Concern synthesis.** Recommend: rule-based, not a separate LLM pass, for V0 -
   e.g. take the lowest-scoring dimension above some weight threshold, contrast it against
   the highest-scoring one, template it into a sentence. Deterministic, testable, no extra
   LLM call, and consistent with readiness %/hire signal already being rule-driven rather
   than model-generated.
