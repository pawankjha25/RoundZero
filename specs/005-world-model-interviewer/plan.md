# 005 - Plan

## Module layout

`src/roundzero/worldmodel/` (core, DB-agnostic - no imports from `apps/`):

| Module | Role (world-model component) |
| --- | --- |
| `config.py` | Loads competencies, dimension->competency map, likelihood table, priors, feature flags |
| `models.py` | Pydantic contracts: Evidence, Belief, Decision, PathPoint, Cause, CompetencyDiagnosis, FlipRewrite, RetryResult, WorldModelReport |
| `belief.py` | **Perceive (state update)** + **Predict**: Bayes update and exact replay |
| `extractor.py` | **Perceive (observation)**: LLMExtractor (Gemini, Flash-Lite via env) and RuleBasedExtractor fallback |
| `picker.py` | **Propose + Evaluate + Decide** (forward): expected information gain over competencies |
| `steering.py` | Renders a live-mode probe hint from `prompts/world_model/probe_hint/v1.md` |
| `diagnosis.py` | Inverse: path, "where it went wrong", causes by exact leave-one-out replay |
| `flip.py` | Counterfactual (hypothetical): writer + blind re-score + replay |
| `retry.py` | Counterfactual (real): score a retried answer, replay with substitution |
| `simulator.py` | Evidence-level simulated candidates; adaptive vs fixed vs random policy comparison |
| `metrics.py` | Weighted kappa, ECE, span precision/recall, log loss |
| `learn.py` | Export transitions, fit likelihood table from data, held-out comparison (Gate 3) |

`apps/api/worldmodel_service.py` - persistence + orchestration glue (session factory
injectable for tests). `apps/api/routes/world_model.py` - HTTP.

## The world model in one line

P(polarity | level, competency) - a 3x4 table per competency (default + overrides),
in `rubrics/competencies/likelihoods_v1.yaml`. Strength s in [0, 1] tempers an item:
L^s. Per turn, total strength per competency is capped at 1 so one long answer with
many items cannot swing the belief alone. Probabilities are floored at 0.01 so a
belief can always recover.

## Data model (append-only, SQLAlchemy, created by `create_all`)

| Table | Rows |
| --- | --- |
| `wm_evidence` | One per extracted evidence item (turn_index, dimension, competency, criterion, polarity, span, strength, extractor_version) |
| `wm_beliefs` | Belief snapshot after each candidate answer (probs per competency) |
| `wm_decisions` | Picker output after each answer (options with EIG, chosen, mode) |
| `wm_rewrites` | Flip rewrites (payload JSON, always hypothetical) |
| `wm_retries` | Real retries (retry text, evidence, before/after means) |

Diagnosis and the path map are **recomputed from events** on read (deterministic,
cheap), so there is no stored report to go stale - per CLAUDE.md "state should be
rebuildable from event history". No ALTER TABLE migrations are needed: all tables
are new.

## Runtime flow

- `orchestrator.post_message`: reads the latest decision -> probe hint (live mode
  only) -> interviewer turn -> commit -> `schedule_after_turn(round_id)`.
- `schedule_after_turn`: runs inline when the extractor is rule-based (instant) or
  `ROUNDZERO_WM_SYNC=1`; otherwise on a daemon thread with its own DB session, so
  the extractor's LLM call never delays the interviewer. Per-round in-process lock
  keeps it idempotent. In live mode the steer therefore lags by one answer.
- `orchestrator.submit_round`: catches up any unprocessed answers synchronously
  before scoring. Any world-model failure is logged and never blocks the round.

## Model choices

| Job | Model | Env |
| --- | --- | --- |
| Extractor + blind re-scorer | Gemini (Flash-Lite intended) | `GEMINI_API_KEY`, `ROUNDZERO_EXTRACTOR_MODEL` (defaults to the interviewer's Gemini model until the Flash-Lite name is set) |
| Flip writer | GPT-5 mini (OpenAIGateway) | `OPENAI_API_KEY` |
| Pre-labeling agent | Anthropic | `ANTHROPIC_API_KEY` |
| Picker, belief, diagnosis | No model - math | - |

## Feature flags

| Env var | Values | Default |
| --- | --- | --- |
| `ROUNDZERO_WM_ENABLED` | 0/1 | 1 |
| `ROUNDZERO_WM_ADAPTIVE` | off / shadow / live | shadow |
| `ROUNDZERO_WM_FLIP` | 0/1 | 1 |
| `ROUNDZERO_WM_SYNC` | 0/1 | auto (inline for rule-based extractor) |

## API

- `GET  /v1/rounds/{id}/world-model` - WorldModelReport (competencies, path, causes, rewrites, retries)
- `POST /v1/rounds/{id}/world-model/rewrites` - generate flip rewrites for the top gaps
- `POST /v1/rounds/{id}/world-model/retries` - `{turn_index, text}` -> RetryResult
- `GET  /v1/report/competency-trend` - final level per competency per evaluated round

## Worked example (from the design doc)

Trade-offs belief before answer 2a: 0.10 / 0.40 / 0.40 / 0.10. Evidence:
contradicted "identifies bottleneck" (strength 0.8). Likelihood of contradicted:
0.40 / 0.20 / 0.08 / 0.05. Posterior (tempered) moves mass toward Senior; the
path map flags 2a as "where it went wrong". Diagnosis removes that item, replays,
and the recovered level is its impact.
