"""
One-off backfill migration for DOG-003 (live dogfooding QA, 2026-09-29).

0008_evaluations_not_assessed.py added the `not_assessed` column and assumed
"No backfill needed - every existing EvaluationRecord row was scored by the
evaluator against a real (possibly thin, but real) transcript under the old
code path, so not_assessed=False ... is correct for all of them." That
assumption turned out to be wrong: a round submitted with literally zero
candidate transcript turns (abandoned right after starting, or ended
immediately) went through the *pre-RZ-02* code path just fine, and got a
fully-scored "0% readiness / NO HIRE" evaluation with a real LLM-generated
per-dimension "no candidate response in the transcript" narrative -
confirmed live against round 8cf33429-17df-4b9f-b03e-38ed6e3fe278 during
dogfooding, evaluated 2026-09-29 06:51, well before the not_assessed check
landed in orchestrator.py (06:51 < 07:36 file mtime that same day).

This migration finds every `evaluations` row that is still `not_assessed=0`
but whose round has zero transcript_turns with speaker='candidate' and
non-empty text, and rewrites it to the same not_assessed shape
apps/api/orchestrator.py::submit_round already produces for a fresh empty
round (see its `if not_assessed:` branch) - readiness_pct=0,
hire_signal='NOT_ASSESSED', dimension_scores/strengths/weaknesses/
improvement_plan all cleared to [], primary_concern set to the same
placeholder string, not_assessed=1. This only touches rows that already
have zero candidate turns; a thin-but-real transcript (one short candidate
answer) is untouched, exactly like the live code path today.

Safe to run more than once (idempotent - re-running finds nothing left to
fix once a row has been backfilled). Run once against the real dev DB:

    python -m apps.api.migrations.0009_backfill_not_assessed
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "apps" / "api" / "roundzero.db"

NOT_ASSESSED_CONCERN = "Not assessed - no responses were submitted before this round ended."


def _column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def run(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"No DB at {db_path} - nothing to backfill.")
        return

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    if not _column_exists(cur, "evaluations", "not_assessed"):
        print("evaluations.not_assessed column doesn't exist yet - run migration 0008 first.")
        con.close()
        return

    # Every evaluation not already flagged not_assessed, whose round has no
    # candidate turn with non-empty text. TRIM handles whitespace-only text
    # the same way orchestrator.py's `t["text"].strip()` check does.
    cur.execute(
        """
        SELECT e.round_id
        FROM evaluations e
        WHERE e.not_assessed = 0
          AND NOT EXISTS (
              SELECT 1 FROM transcript_turns t
              WHERE t.round_id = e.round_id
                AND t.speaker = 'candidate'
                AND TRIM(t.text) != ''
          )
        """
    )
    stale_round_ids = [row[0] for row in cur.fetchall()]

    if not stale_round_ids:
        print("No stale evaluations found - nothing to backfill.")
        con.close()
        return

    empty_json = json.dumps([])
    cur.executemany(
        """
        UPDATE evaluations
        SET dimension_scores = ?,
            readiness_pct = 0,
            hire_signal = 'NOT_ASSESSED',
            primary_concern = ?,
            strengths = ?,
            weaknesses = ?,
            improvement_plan = ?,
            not_assessed = 1
        WHERE round_id = ?
        """,
        [
            (empty_json, NOT_ASSESSED_CONCERN, empty_json, empty_json, empty_json, round_id)
            for round_id in stale_round_ids
        ],
    )
    con.commit()
    con.close()
    print(f"Backfilled {len(stale_round_ids)} stale evaluation(s) to not_assessed=1: {stale_round_ids}")


if __name__ == "__main__":
    run()
