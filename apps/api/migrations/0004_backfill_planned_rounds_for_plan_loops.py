"""
One-off backfill for User-Defined Prep Plans (Prep Plans feature).

orchestrator.start_round_from_plan_question creates its own fresh
one-round loop for every round started from a plan question (same shape
create_round already uses for the /setup quick-start path), but until this
was fixed it never wrote the matching PlannedRound row create_round always
writes alongside it - breaking the "every RoundAttempt has exactly one
PlannedRound" invariant PlannedRound's own docstring describes (see
apps/api/models.py). The visible symptom (caught live 2026-09-03): the
dashboard's Upcoming section showed "Plan-Generic ... - 0 of 0 interviews
started" for a loop that actually had one real, possibly-already-evaluated
round attempt in it.

orchestrator.py is fixed going forward - this script backfills the
PlannedRound rows for any "Plan-*" loop that's missing one, exactly the way
0001_loops_and_tiers.py backfilled the 10 pre-feature RoundAttempt rows when
PlannedRound itself was introduced.

Safe to run more than once - only inserts a PlannedRound for a Plan-* round
attempt that doesn't already have one.

Run once against the real dev DB:

    python -m apps.api.migrations.0004_backfill_planned_rounds_for_plan_loops
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "apps" / "api" / "roundzero.db"


def run(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"No DB at {db_path} - nothing to migrate.")
        return

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    cur.execute(
        """
        SELECT l.id, r.id, r.round_type, r.role_family, r.level, r.domain,
               r.company_profile, r.duration_minutes, r.modality
        FROM loop_attempts l
        JOIN round_attempts r ON r.loop_attempt_id = l.id
        WHERE l.name LIKE 'Plan-%'
          AND NOT EXISTS (SELECT 1 FROM planned_rounds p WHERE p.round_attempt_id = r.id)
        """
    )
    rows = cur.fetchall()

    for loop_id, round_id, round_type, role_family, level, domain, company_profile, duration_minutes, modality in rows:
        cur.execute(
            """
            INSERT INTO planned_rounds
                (id, loop_attempt_id, user_id, round_type, role_family, level, domain,
                 company_profile, duration_minutes, modality, sort_order, round_attempt_id)
            SELECT ?, ?, user_id, ?, ?, ?, ?, ?, ?, ?, 0, ?
            FROM loop_attempts WHERE id = ?
            """,
            (
                str(uuid.uuid4()),
                loop_id,
                round_type,
                role_family,
                level,
                domain,
                company_profile,
                duration_minutes,
                modality,
                round_id,
                loop_id,
            ),
        )
        print(f"Backfilled planned_round for loop {loop_id} (round {round_id})")

    if not rows:
        print("Nothing to backfill - every Plan-* round already has a planned_round.")

    con.commit()
    con.close()
    print("Backfill complete.")


if __name__ == "__main__":
    run()
