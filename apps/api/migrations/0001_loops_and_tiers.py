"""
One-off migration for the Loop Planner + company tiers feature.

Base.metadata.create_all() (apps/api/main.py) only ever CREATEs new tables -
it never ALTERs an existing one, so the two new columns below need a manual
ALTER TABLE before the app is restarted with the updated models.py, or every
query touching LoopAttempt/CompanyProfileOption breaks with "no such column".
planned_rounds itself doesn't need a manual CREATE TABLE - create_all() picks
up the brand-new PlannedRound model automatically on next app startup - but
it's created here too (IF NOT EXISTS) so this script is safe to run standalone,
before the app has ever started with the new model.

Safe to run more than once (every step checks first). Run once against the
real dev DB:

    python -m apps.api.migrations.0001_loops_and_tiers

Backfill is real-data-only, never fabricated:
- loop_attempts.name for the 10 pre-feature rows is derived from that loop's
  own (single, today) round's role_family/level/company_profile/created_at -
  data that already exists on that row, just reformatted into a label.
- planned_rounds backfill wraps every existing round_attempts row in exactly
  one PlannedRound with round_attempt_id pointing at itself and the row's own
  real config copied across (role_family/level/domain/company_profile/
  duration_minutes/modality/round_type) - nothing invented.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "apps" / "api" / "roundzero.db"


def _column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def run(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"No DB at {db_path} - nothing to migrate (a fresh app start will create the full schema).")
        return

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    # 1. loop_attempts.name
    if not _column_exists(cur, "loop_attempts", "name"):
        cur.execute("ALTER TABLE loop_attempts ADD COLUMN name TEXT")
        print("Added loop_attempts.name")
    else:
        print("loop_attempts.name already present")

    # 2. company_profile_options.tier
    if not _column_exists(cur, "company_profile_options", "tier"):
        cur.execute("ALTER TABLE company_profile_options ADD COLUMN tier TEXT")
        print("Added company_profile_options.tier")
    else:
        print("company_profile_options.tier already present")

    # 3. planned_rounds table (mirrors apps/api/models.py::PlannedRound)
    if not _table_exists(cur, "planned_rounds"):
        cur.execute(
            """
            CREATE TABLE planned_rounds (
                id VARCHAR NOT NULL PRIMARY KEY,
                loop_attempt_id VARCHAR NOT NULL,
                user_id VARCHAR NOT NULL,
                round_type VARCHAR NOT NULL,
                role_family VARCHAR NOT NULL,
                level VARCHAR NOT NULL,
                domain VARCHAR NOT NULL,
                company_profile VARCHAR NOT NULL DEFAULT 'generic',
                duration_minutes INTEGER NOT NULL,
                modality VARCHAR NOT NULL DEFAULT 'text',
                sort_order INTEGER NOT NULL DEFAULT 0,
                round_attempt_id VARCHAR,
                created_at DATETIME,
                FOREIGN KEY(loop_attempt_id) REFERENCES loop_attempts (id),
                FOREIGN KEY(round_attempt_id) REFERENCES round_attempts (id)
            )
            """
        )
        cur.execute("CREATE INDEX ix_planned_rounds_loop_attempt_id ON planned_rounds (loop_attempt_id)")
        cur.execute("CREATE INDEX ix_planned_rounds_user_id ON planned_rounds (user_id)")
        print("Created planned_rounds table")
    else:
        print("planned_rounds table already present")

    con.commit()

    # 4. Backfill loop_attempts.name for existing rows (derived from that
    # loop's own round data - every pre-feature loop has exactly one round).
    cur.execute(
        """
        SELECT l.id, r.role_family, r.level, r.company_profile, l.created_at
        FROM loop_attempts l
        JOIN round_attempts r ON r.loop_attempt_id = l.id
        WHERE l.name IS NULL
        """
    )
    rows = cur.fetchall()
    # Same abbreviation fix as apps/api/orchestrator.py::_derive_loop_name -
    # str.capitalize() alone turns "ml" into "Ml", whose lowercase "l" is
    # visually indistinguishable from a capital "I" in any sans-serif UI
    # font ("Ml Engineer" reads as "MI Engineer"). Kept in sync manually
    # since this script and orchestrator.py don't share an import today.
    label_overrides = {"ml": "ML"}

    def _title_word(word: str) -> str:
        return label_overrides.get(word, word.capitalize())

    for loop_id, role_family, level, company_profile, created_at in rows:
        date_part = (created_at or "")[:10]
        label = " ".join(_title_word(w) for w in f"{level}_{role_family}".split("_"))
        company_label = " ".join(_title_word(w) for w in company_profile.split("_"))
        name = f"{company_label} - {label}" + (f" ({date_part})" if date_part else "")
        cur.execute("UPDATE loop_attempts SET name = ? WHERE id = ?", (name, loop_id))
    if rows:
        print(f"Backfilled {len(rows)} loop name(s)")
    con.commit()

    # Any loop with genuinely no round at all (shouldn't exist today, but
    # don't leave a NULL name if one somehow does) gets an honest fallback.
    cur.execute("UPDATE loop_attempts SET name = 'Untitled loop' WHERE name IS NULL")
    con.commit()

    # 5. Backfill one PlannedRound per existing RoundAttempt, wrapping it.
    cur.execute(
        """
        SELECT r.id, r.loop_attempt_id, r.user_id, r.round_type, r.role_family,
               r.level, r.domain, r.company_profile, r.duration_minutes,
               r.modality, r.created_at
        FROM round_attempts r
        LEFT JOIN planned_rounds p ON p.round_attempt_id = r.id
        WHERE p.id IS NULL
        """
    )
    rounds = cur.fetchall()
    import uuid

    for (
        round_id,
        loop_attempt_id,
        user_id,
        round_type,
        role_family,
        level,
        domain,
        company_profile,
        duration_minutes,
        modality,
        created_at,
    ) in rounds:
        cur.execute(
            """
            INSERT INTO planned_rounds (
                id, loop_attempt_id, user_id, round_type, role_family, level,
                domain, company_profile, duration_minutes, modality,
                sort_order, round_attempt_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                loop_attempt_id,
                user_id,
                round_type,
                role_family,
                level,
                domain,
                company_profile,
                duration_minutes,
                modality,
                round_id,
                created_at,
            ),
        )
    if rounds:
        print(f"Backfilled {len(rounds)} planned_round row(s)")
    con.commit()
    con.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()
