"""
One-off backfill for the ML Depth round type (2026-09-03) - see
src/roundzero/interviewers/ml_depth/agent.py, rubrics/ml_depth/v1.yaml, and
prompts/interviewers/ml_depth/scenarios.yaml.

apps/api/seed.py::seed_defaults() only ever inserts into a table that is
completely empty (see its own docstring), so it never adds a row to a table
that's already been seeded once - which the real dev DB has been since
Milestone 1. This script adds the two rows that pass needs on an
already-seeded DB:

1. domain_options: "reinforcement_learning" - Setup's Domain dropdown reads
   this table directly, and ml_depth's scenarios.yaml tags real scenarios
   with this domain, so without this row a candidate can never actually
   select the Reinforcement Learning sub-area.
2. round_type_options: flips "coding" and "ml_depth" to enabled=True - purely
   cosmetic/admin-facing (see RoundTypeOption's docstring in models.py; the
   Practice page's card list is a separate static frontend array, not driven
   by this table), kept in sync for the admin round-types panel's own sake.

Safe to run more than once (every step checks first). Run once against the
real dev DB:

    python -m apps.api.migrations.0003_ml_depth
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "apps" / "api" / "roundzero.db"


def run(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"No DB at {db_path} - nothing to migrate (a fresh app start will seed the full schema).")
        return

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    # PERSIST avoids deleting the rollback-journal file on commit (just
    # truncates it in place) - the default DELETE journal mode fails with
    # "disk I/O error" on some mounted/networked filesystems that don'''t
    # support unlinking a file mid-transaction the way local disk does. This
    # only affects this one connection, not the live app's own connections.
    cur.execute("PRAGMA journal_mode=PERSIST")

    # 1. domain_options: reinforcement_learning
    cur.execute("SELECT 1 FROM domain_options WHERE value = ?", ("reinforcement_learning",))
    if cur.fetchone() is None:
        cur.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM domain_options")
        next_sort = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO domain_options (value, label, sort_order) VALUES (?, ?, ?)",
            ("reinforcement_learning", "Reinforcement Learning", next_sort),
        )
        print("Added domain_options.reinforcement_learning")
    else:
        print("domain_options.reinforcement_learning already present")

    # 2. round_type_options: enable coding + ml_depth
    for value in ("coding", "ml_depth"):
        cur.execute("SELECT enabled FROM round_type_options WHERE value = ?", (value,))
        row = cur.fetchone()
        if row is None:
            print(f"round_type_options.{value} not found - skipping (unexpected: seed_defaults should have created it)")
        elif row[0] in (0, False):
            cur.execute("UPDATE round_type_options SET enabled = 1 WHERE value = ?", (value,))
            print(f"Enabled round_type_options.{value}")
        else:
            print(f"round_type_options.{value} already enabled")

    con.commit()
    con.close()


if __name__ == "__main__":
    run()
