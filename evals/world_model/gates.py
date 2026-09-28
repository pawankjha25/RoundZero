"""
Gate 1: is the world model's evidence, level read and diagnosis trustworthy
enough to ship? (specs/005, evals/world_model/README.md)

    python -m evals.world_model.gates

Reads reviewed label files (labels/*.json with "reviewed": true), recomputes
the system's output for each round from the wm_* event tables, and reports:
evidence span precision/recall, level agreement (quadratic weighted kappa),
calibration (ECE), gap agreement, unsupported-claim rate, and the flip rate of
generated rewrites.
"""
from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from apps.api.db import SessionLocal  # noqa: E402
from apps.api.models import RoundAttempt, WMRewrite  # noqa: E402
from apps.api.worldmodel_service import load_evidence, turn_dicts  # noqa: E402
from roundzero.worldmodel import config, metrics  # noqa: E402
from roundzero.worldmodel.diagnosis import diagnose  # noqa: E402
from roundzero.worldmodel.extractor import span_in_answer  # noqa: E402

LABELS_DIR = Path(__file__).resolve().parent / "labels"
THRESHOLDS = {"precision": 0.80, "recall": 0.70, "kappa": 0.60, "ece_max": 0.10, "unsupported_max": 0.05,
              "min_rounds": 60}


def main() -> None:
    files = sorted(LABELS_DIR.glob("*.json")) if LABELS_DIR.exists() else []
    labels = [json.loads(f.read_text()) for f in files]
    reviewed = [lb for lb in labels if lb.get("reviewed")]
    print(f"label files: {len(labels)}, reviewed: {len(reviewed)}")
    if not reviewed:
        print("No reviewed labels yet - run evals.world_model.prelabel, review the drafts, set reviewed=true.")
        return

    levels = config.level_keys()
    pred_spans, gold_spans = [], []
    sys_levels, gold_levels, confidences, correct = [], [], [], []
    gap_hits = gap_total = 0
    unsupported = total_items = 0
    flips = rewrites = 0

    with SessionLocal() as db:
        for lb in reviewed:
            r = db.get(RoundAttempt, lb["round_id"])
            if r is None:
                print(f"missing round {lb['round_id']} - skipped")
                continue
            turns = turn_dicts(db, r.id)
            text_by_turn = {t["turn_index"]: t["text"] for t in turns}
            evidence = load_evidence(db, r.id)
            key = r.id
            for e in evidence:
                pred_spans.append((f"{key}:{e.turn_index}", e.polarity, e.span or ""))
                total_items += 1
                if e.polarity != "absent" and not span_in_answer(e.span, text_by_turn.get(e.turn_index, "")):
                    unsupported += 1
            for g in lb.get("evidence", []):
                gold_spans.append((f"{key}:{g['turn_index']}", g["polarity"], g.get("span") or ""))

            diags = {d.competency: d for d in diagnose(round_type=r.round_type, target_level=r.level,
                                                        turns=turns, evidence=evidence)}
            for comp, gold in (lb.get("levels") or {}).items():
                d = diags.get(comp)
                if d is None or d.abstained or gold not in levels:
                    continue
                s_idx, g_idx = levels.index(d.final_level), levels.index(gold)
                sys_levels.append(s_idx)
                gold_levels.append(g_idx)
                confidences.append(d.confidence)
                correct.append(s_idx == g_idx)
            for gap in lb.get("gaps", []):
                d = diags.get(gap.get("competency"))
                gap_total += 1
                if d and d.causes and d.causes[0].turn_index == gap.get("turn_index"):
                    gap_hits += 1
            for rw in db.query(WMRewrite).filter(WMRewrite.round_id == r.id):
                rewrites += 1
                flips += bool(rw.payload.get("flipped"))

    precision, recall = metrics.span_precision_recall(pred_spans, gold_spans)
    kappa = metrics.quadratic_weighted_kappa(sys_levels, gold_levels)
    ece = metrics.expected_calibration_error(confidences, correct)
    unsupported_rate = unsupported / total_items if total_items else 0.0

    rows = [
        ("reviewed rounds", len(reviewed), f">= {THRESHOLDS['min_rounds']}", len(reviewed) >= THRESHOLDS["min_rounds"]),
        ("span precision", round(precision, 3), f">= {THRESHOLDS['precision']}", precision >= THRESHOLDS["precision"]),
        ("span recall", round(recall, 3), f">= {THRESHOLDS['recall']}", recall >= THRESHOLDS["recall"]),
        ("level kappa", round(kappa, 3), f">= {THRESHOLDS['kappa']}", kappa >= THRESHOLDS["kappa"]),
        ("calibration ECE", round(ece, 3), f"< {THRESHOLDS['ece_max']}", ece < THRESHOLDS["ece_max"]),
        ("unsupported claims", round(unsupported_rate, 3), f"< {THRESHOLDS['unsupported_max']}",
         unsupported_rate < THRESHOLDS["unsupported_max"]),
    ]
    for name, value, target, ok in rows:
        print(f"  {name:20s} {value!s:>8}  target {target:8s} {'ok' if ok else 'MISS'}")
    print(f"  {'gap agreement':20s} {gap_hits}/{gap_total}  (top cause on the labeled turn)")
    print(f"  {'flip rate':20s} {flips}/{rewrites}  (target 70%+, blind re-score)")
    print(f"\nGate 1: {'PASS' if all(ok for *_, ok in rows) else 'NOT YET'} (level pairs scored: {len(sys_levels)})")


if __name__ == "__main__":
    main()
