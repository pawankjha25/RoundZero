"""
One-off migration for RZ-02 (UI/UX review, 2026-09-29 - "empty round scored
as if it were a genuine 0% / NO HIRE failure").

Same rationale as every prior numbered migration here: Base.metadata.
create_all() only ever CREATEs new tables, never ALTERs an existing one, so
a pre-existing local roundzero.db's `evaluations` table needs this column
added by hand before the app is restarted with the updated models.py, or
every query touching EvaluationRecord breaks with "no such column:
evaluations.not_assessed" (same class of failure 0006 fixed for
users.stripe_customer_id).

No backfill needed - every existing EvaluationRecord row was scored by the
evaluator against a real (possibly thin, but real) transcript under the old
code path, so `not_assessed=False` (the column default) is correct for all
of them. Only rounds submitted after this migration + the orchestrator.py
fix can ever get `not_assessed=True`.

Safe to run more than once. Run once against the real dev DB:

    python -m apps.api.migrations.0008_evaluations_not_assessed
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

    if not _column_exists(cur, "evaluations", "not_assessed"):
        # SQLite's ALTER TABLE ADD COLUMN requires a constant default when
        # the table already has rows - 0 (false) here, matching the
        # column's nullable=False default=False in models.py.
        cur.execute("ALTER TABLE evaluations ADD COLUMN not_assessed BOOLEAN NOT NULL DEFAULT 0")
        print("Added evaluations.not_assessed")
    else:
        print("evaluations.not_assessed already present")

    con.commit()
    con.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()
