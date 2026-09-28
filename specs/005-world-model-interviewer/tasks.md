# 005 - Tasks

## Foundations
- [x] Competencies v1 + dimension map (`rubrics/competencies/v1.yaml`)
- [x] Likelihood table, priors, update and diagnosis settings (`rubrics/competencies/likelihoods_v1.yaml`)
- [x] Versioned prompts: extractor, flip_rewrite, probe_hint, labeler, sim_candidate (`prompts/world_model/`)
- [x] Contracts (`src/roundzero/worldmodel/models.py`) and config/flags (`config.py`)
- [x] Append-only tables `wm_evidence`, `wm_processed_turns`, `wm_beliefs`, `wm_decisions`, `wm_rewrites`, `wm_retries`

## Diagnosis
- [x] Extractor (Gemini) + rule-based fallback, with the unsupported-claim guard
- [x] Bayes belief update + exact replay
- [x] Tracking hook in `orchestrator.post_message` (inline or background thread) and catch-up at submit
- [x] Diagnosis: path, where it went wrong, leave-one-out causes, abstain
- [x] `GET /v1/rounds/{id}/world-model` (409 while the round is live)
- [x] Report page: interview path map + answer drawer
- [ ] Set `ROUNDZERO_EXTRACTOR_MODEL` to the Flash-Lite model name available to the Gemini key
- [ ] Label 60 rounds (prelabel -> Pawan review) and run Gate 1

## Flip and retry
- [x] Flip writer (GPT-5 mini) + blind re-score (extractor) + projection
- [x] `POST /world-model/rewrites` (on demand), `POST /world-model/retries`
- [x] Path map: dashed fix branch, solid retry branch; drawer: smallest fix, retry form
- [x] Progress page: level by competency across sessions (`GET /v1/report/competency-trend`)

## Adaptive asks
- [x] Picker (expected information gain + constraints), logged every answer
- [x] `probe_hint` threaded through all six interviewer agents (live mode only)
- [x] Evidence-level simulator + `evals/world_model/run_simulation.py`
- [ ] Gate 2 - FAILS in simulation today (adaptive needs 0-20% fewer questions vs the 25% target); keep `ROUNDZERO_WM_ADAPTIVE=shadow`, re-run after Gate 3 refits the table, then check real rounds from `wm_decisions`
- [ ] Text-level simulated candidates wired into a nightly regression run

## Learned model
- [x] Export transitions / decisions / retry pairs; Laplace-smoothed fitter; held-out comparison (`evals/world_model/export_and_fit.py`)
- [ ] Gate 3 on reviewed labels; if the fitted table wins, add it as `likelihoods_v2.yaml`

## Known limits
- The v1 likelihood table is weakly discriminative between adjacent levels: in simulation, 25 single-item probes reach ~58-71% exact-level accuracy. Expect wide confidence bands on one round until Gate 3 refits the table.
- In live mode the probe hint lags one answer when the LLM extractor runs on a background thread.
- Coding rounds map only two dimensions to competencies (no coding competency in v1).
