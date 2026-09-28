"""
One-off migration for "Practice this weakness" (Drills feature).

Same rationale as 0003_prep_plan_question_id.py: Base.metadata.create_all()
only ever CREATEs new tables, never ALTERs an existing one. round_attempts
already exists, so its new drill_focus_hint column needs a manual
ALTER TABLE before the app is restarted with the updated models.py, or any
round-starting/continuing query breaks with
"no such column: round_attempts.drill_focus_hint".

No backfill needed - drill_focus_hint is nullable and every existing row
(created before this feature existed) is correctly left NULL.

Safe to run more than once. Run once against the real dev DB:

    python -m apps.api.migrations.0005_drill_focus_hint
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

    if not _column_exists(cur, "round_attempts", "drill_focus_hint"):
        cur.execute("ALTER TABLE round_attempts ADD COLUMN drill_focus_hint VARCHAR")
        print("Added round_attempts.drill_focus_hint")
    else:
        print("round_attempts.drill_focus_hint already present")

    con.commit()
    con.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()
