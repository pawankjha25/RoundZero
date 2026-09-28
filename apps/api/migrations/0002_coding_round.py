"""
One-off migration for the Coding round type (specs/004-coding-round-type).

Same rationale as 0001_loops_and_tiers.py: Base.metadata.create_all() only
ever CREATEs new tables, never ALTERs an existing one, so the new
round_attempts.scenario_meta column needs a manual ALTER TABLE before the app
is restarted with the updated models.py, or every query touching
RoundAttempt breaks with "no such column".

No backfill needed - scenario_meta is nullable and every existing row (all
ml_system_design) is correctly left NULL; nothing was ever removed or
reshaped for those rows.

Safe to run more than once. Run once against the real dev DB:

    python -m apps.api.migrations.0002_coding_round
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

    if not _column_exists(cur, "round_attempts", "scenario_meta"):
        cur.execute("ALTER TABLE round_attempts ADD COLUMN scenario_meta TEXT")
        print("Added round_attempts.scenario_meta")
    else:
        print("round_attempts.scenario_meta already present")

    con.commit()
    con.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()
