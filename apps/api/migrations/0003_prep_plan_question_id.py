"""
One-off migration for User-Defined Prep Plans (Prep Plans feature).

Same rationale as 0001_loops_and_tiers.py and 0002_coding_round.py:
Base.metadata.create_all() only ever CREATEs new tables, never ALTERs an
existing one. prep_plans/prep_plan_areas/prep_plan_questions are brand new
tables, so create_all() picked those up fine on server startup - but
round_attempts already existed, so its new prep_plan_question_id column
needs a manual ALTER TABLE before the app is restarted with the updated
models.py, or any query touching RoundAttempt/question_progress breaks with
"no such column: round_attempts.prep_plan_question_id" (seen live via the
Chrome verification pass on 2026-09-03 - "+ Add from bank" 500'd because the
new question's progress badge is computed with a query against this column
immediately after insert).

No backfill needed - prep_plan_question_id is nullable and every existing
row (created before this feature existed) is correctly left NULL.

Safe to run more than once. Run once against the real dev DB:

    python -m apps.api.migrations.0003_prep_plan_question_id
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "apps" / "api" / "roundzero.db"


def _column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def run(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"No DB at {db_path} - nothing to migrate (a fresh app start will create the full schema).")
        return

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    if not _column_exists(cur, "round_attempts", "prep_plan_question_id"):
        cur.execute("ALTER TABLE round_attempts ADD COLUMN prep_plan_question_id VARCHAR")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_round_attempts_prep_plan_question_id "
            "ON round_attempts (prep_plan_question_id)"
        )
        print("Added round_attempts.prep_plan_question_id (+ index)")
    else:
        print("round_attempts.prep_plan_question_id already present")

    con.commit()
    con.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()
