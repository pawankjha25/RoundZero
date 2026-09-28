# evals/world_model/

Gate tooling for the world-model interviewer (specs/005-world-model-interviewer).
Run everything from the repo root with the API's venv active.

| Script | Gate | What it does |
| --- | --- | --- |
| `run_simulation.py` | Gate 2 (offline) | Adaptive vs fixed vs random follow-up order on evidence-level simulated candidates |
| `prelabel.py` | Gate 1 input | AI labeling agent (Anthropic) drafts labels for evaluated rounds into `labels/` for review |
| `gates.py` | Gate 1 | Compares the system's evidence, levels and diagnoses with reviewed labels |
| `export_and_fit.py` | Gate 3 | Exports transitions and retry pairs, fits the likelihood table, compares on held-out rounds |

## Labeling workflow (decided 2026-09-28)

1. `python -m evals.world_model.prelabel --limit 20` writes `labels/<round_id>.json`
   with `"reviewed": false`. Needs `ANTHROPIC_API_KEY` - a different vendor from the
   Gemini extractor and the GPT-5 mini evaluator, so labels are not the system
   grading itself.
2. Open each file, correct levels, spans and gaps, then set `"reviewed": true` and
   `"reviewer": "pawan"`.
3. `python -m evals.world_model.gates` reports Gate 1 metrics on reviewed files only.
4. Before any public accuracy claim, have an external Staff-level engineer check
   about 20 reviewed files and record `"external_check": true`.

`labels/` holds candidate transcripts' derived data - only rounds with training
consent belong there, and it should stay out of git.

## Gate thresholds (starting targets, revisit after the first labeled batch)

- Gate 1: span precision >= 0.80, recall >= 0.70, level kappa >= 0.60, ECE < 0.10,
  unsupported claims < 5%, on >= 60 reviewed rounds.
- Gate 2: adaptive order reaches the fixed order's final accuracy with at least
  25% fewer questions (simulator first, then real rounds via `wm_decisions`).
- Gate 3: the fitted table has lower held-out log loss than the v1 table.
