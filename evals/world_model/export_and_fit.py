"""
Gate 3: export the data a learned world model needs, fit the likelihood table
from reviewed labels, and compare it with the hand-set v1 table on held-out
rounds (specs/005, roundzero.worldmodel.learn).

    python -m evals.world_model.export_and_fit

Writes, under evals/world_model/out/:
- transitions.jsonl  - (round, competency, reviewed level, polarity) per evidence item
- decisions.jsonl    - every logged picker decision (for offline Gate 2 on real rounds)
- retries.jsonl      - real before/after retry pairs (the only true counterfactual data)
- likelihoods_fitted.yaml - ONLY a proposal; copy into rubrics/competencies/ as a new
  version by hand if fitted_wins, never overwrite v1 in place.
Flip rewrites are never exported - they are hypothetical.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from apps.api.db import SessionLocal  # noqa: E402
from apps.api.models import WMDecision, WMRetry  # noqa: E402
from roundzero.worldmodel import config, learn  # noqa: E402

HERE = Path(__file__).resolve().parent
LABELS_DIR = HERE / "labels"
OUT_DIR = HERE / "out"


def reviewed_transitions() -> list[learn.Transition]:
    levels = config.level_keys()
    out: list[learn.Transition] = []
    for f in sorted(LABELS_DIR.glob("*.json")) if LABELS_DIR.exists() else []:
        lb = json.loads(f.read_text())
        if not lb.get("reviewed"):
            continue
        gold_levels = lb.get("levels") or {}
        for g in lb.get("evidence", []):
            comp = config.dimension_to_competency(lb["round_type"], g.get("dimension", ""))
            gold = gold_levels.get(comp or "")
            if comp and gold in levels and g.get("polarity") in config.POLARITIES:
                out.append((lb["round_id"], comp, levels.index(gold), g["polarity"]))
    return out


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    transitions = reviewed_transitions()
    with (OUT_DIR / "transitions.jsonl").open("w") as f:
        for rid, comp, lvl, pol in transitions:
            f.write(json.dumps({"round_id": rid, "competency": comp, "level": lvl, "polarity": pol}) + "\n")

    with SessionLocal() as db:
        with (OUT_DIR / "decisions.jsonl").open("w") as f:
            for d in db.query(WMDecision).order_by(WMDecision.round_id, WMDecision.after_turn_index):
                f.write(json.dumps({"round_id": d.round_id, "after_turn_index": d.after_turn_index,
                                    "mode": d.mode, **d.payload}, default=str) + "\n")
        n_retries = 0
        with (OUT_DIR / "retries.jsonl").open("w") as f:
            for r in db.query(WMRetry).order_by(WMRetry.created_at):
                f.write(json.dumps({"round_id": r.round_id, "turn_index": r.turn_index, **r.payload},
                                   default=str) + "\n")
                n_retries += 1

    print(f"exported {len(transitions)} transitions, {n_retries} retry pairs")
    if len({t[0] for t in transitions}) < 5:
        print("Gate 3: NOT YET - need reviewed labels from at least 5 rounds to fit and hold out.")
        return
    report = learn.compare_on_heldout(transitions)
    (OUT_DIR / "likelihoods_fitted.yaml").write_text(yaml.safe_dump(report["fitted_table"], sort_keys=False))
    print(f"held-out log loss: v1 table {report['log_loss_v1_table']}, fitted {report['log_loss_fitted']} "
          f"({report['train_transitions']} train / {report['test_transitions']} test transitions)")
    print(f"Gate 3: {'PASS - review out/likelihoods_fitted.yaml as likelihoods_v2' if report['fitted_wins'] else 'NOT YET'}")


if __name__ == "__main__":
    main()
