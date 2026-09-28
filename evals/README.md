# evals/

Treated as first-class production code (see CLAUDE.md decision 3). Every prompt, model, or
rubric change must be regression-tested against this suite before it ships.

- golden/       - golden interview transcripts with expert-labeled evidence + expected score bands
- interviewer/  - interviewer quality tests: relevance, follow-up quality, hint leakage, repetition, difficulty calibration, time management
- evaluator/    - evaluator tests: evidence grounding, score stability, false-positive/negative weaknesses, level calibration
- debrief/      - cross-round synthesis tests
- adversarial/  - prompt injection, rubric-extraction attempts, nonsensical answers, overconfident bluffing
- regression/   - regression suite run on every prompt/rubric/model change

See docs/PRD.md section 28.
