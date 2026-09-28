"""
AI pre-labeling agent (decided 2026-09-28): drafts labels for evaluated rounds
that Pawan then reviews and corrects (specs/005, evals/world_model/README.md).

    python -m evals.world_model.prelabel [--limit 20] [--round-id ID] [--overwrite]

Uses AnthropicGateway - deliberately a different vendor from the Gemini
extractor and the GPT-5 mini evaluator. Writes labels/<round_id>.json with
"reviewed": false; never overwrites a reviewed file.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from apps.api.db import SessionLocal  # noqa: E402
from apps.api.models import RoundAttempt  # noqa: E402
from apps.api.worldmodel_service import turn_dicts  # noqa: E402
from roundzero.evaluation.rubric_loader import load_rubric  # noqa: E402
from roundzero.worldmodel import config  # noqa: E402

LABELS_DIR = Path(__file__).resolve().parent / "labels"
PROMPT_VERSION = "v1"


def build_user_message(round_: RoundAttempt, turns: list[dict]) -> str:
    comps = "\n".join(
        f"- {c['key']}: {c['label']} - Staff vs Senior: {c['staff_vs_senior']}"
        for c in config.load_competencies()["competencies"]
    )
    dims = "\n".join(
        f"- {d['key']} ({d['label']}) -> {config.dimension_to_competency(round_.round_type, d['key']) or 'cross-cutting'}"
        for d in load_rubric(round_.round_type)["dimensions"]
    )
    transcript = "\n".join(f"[{t['turn_index']}] {t['speaker']}: {t['text']}" for t in turns)
    return (
        f"Round type: {round_.round_type}; target level: {round_.level}\n\n"
        f"Competencies:\n{comps}\n\nRubric dimensions -> competency:\n{dims}\n\n"
        f"Transcript:\n{transcript}\n\nReturn the JSON object described in your instructions."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--round-id")
    parser.add_argument("--overwrite", action="store_true", help="replace unreviewed drafts")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set - the labeling agent must be a different vendor from the "
                         "extractor (Gemini) and evaluator (GPT-5 mini).")
    from roundzero.llm.providers.anthropic_provider import AnthropicGateway

    llm = AnthropicGateway()
    system = config.load_wm_prompt("labeler", PROMPT_VERSION)
    LABELS_DIR.mkdir(exist_ok=True)

    with SessionLocal() as db:
        q = db.query(RoundAttempt).filter(RoundAttempt.status == "EVALUATED")
        if args.round_id:
            q = q.filter(RoundAttempt.id == args.round_id)
        rounds = q.order_by(RoundAttempt.created_at.desc()).limit(args.limit).all()
        for r in rounds:
            path = LABELS_DIR / f"{r.id}.json"
            if path.exists():
                existing = json.loads(path.read_text())
                if existing.get("reviewed") or not args.overwrite:
                    print(f"skip {r.id} (exists{', reviewed' if existing.get('reviewed') else ''})")
                    continue
            turns = turn_dicts(db, r.id)
            if not turns:
                continue
            raw = llm.complete_json(system=system, user_message=build_user_message(r, turns), max_tokens=4096)
            draft = json.loads(raw)
            draft.update({
                "round_id": r.id,
                "round_type": r.round_type,
                "reviewed": False,
                "reviewer": None,
                "external_check": False,
                "labeler": f"anthropic-labeler-{PROMPT_VERSION}",
                "drafted_at": datetime.now(timezone.utc).isoformat(),
            })
            path.write_text(json.dumps(draft, indent=2))
            print(f"drafted {path.name}")


if __name__ == "__main__":
    main()
