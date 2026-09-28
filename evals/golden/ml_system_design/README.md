# evals/golden/ml_system_design

10 golden fixtures under `fixtures/*.json`, regression-tested by `test_golden.py`
(run `pytest evals/ -q` from the repo root). Each fixture is a
(transcript, final_coverage) pair plus the exact expected dimension_scores/
readiness_pct/hire_signal - see `test_golden.py`'s own docstring for why
"exact match" is the right assertion here (RuleBasedEvaluator is a pure,
deterministic function of its inputs - no LLM, no network).

Scope, honestly: these fixtures were built synthetically (`generate_fixtures.py`)
to exercise the scoring algorithm's boundaries - every hire-signal band, the
COVERED-with-3+-evidence "exceeds target" bump, a realistic partial-round shape
- and are self-consistent (the "expected" values are RuleBasedEvaluator's own
real output, captured once and pinned). They are NOT independently
expert-labeled transcripts reviewed by a human interviewer against the rubric,
which is what docs/PRD.md section 37 / ticket 11 originally asked for and what
LLMEvaluator (once it has its own, band-based, non-deterministic golden suite)
will actually need. This suite protects the deterministic scoring algorithm
from silent regressions; it doesn't yet validate that the rubric's calibration
matches real expert judgment - that's the honest gap left for a follow-up pass,
tracked here rather than left implicit.
