"""
One-off migration: enforce uniqueness on users.email.

Same rationale as every prior numbered migration here: Base.metadata.
create_all() only ever CREATEs new tables, never ALTERs an existing column's
constraints. users.email was originally created without a UNIQUE constraint
(see models.py::User's docstring history) - a real duplicate showed up in
dev on 2026-09-29 (Google sign-in and the email magic link minted two
different Supabase auth.users ids for pawan.jha25@gmail.com, so
get_current_user's id-only upsert created two separate local User rows -
two separate entitlements for what's really one person). apps/api/deps.py
now handles a UNIQUE collision gracefully (falls back to an email lookup
and reuses the existing row instead of 500ing), so it's safe to add the
constraint for real.

SQLite can't ALTER TABLE ... ADD CONSTRAINT UNIQUE after the fact, but a
UNIQUE INDEX enforces the same guarantee. Requires no duplicate emails to
already exist - this migration refuses to run (rather than silently
picking a "winner") if it finds any, since deciding which duplicate row to
keep/merge is a judgment call for a human, not a migration script. Delete
or merge duplicates by hand first if this happens to you (see the
2026-09-29 fix in this repo's history for exactly that: find the
lower-activity duplicate row, confirm it has no meaningful data attached,
delete it, then re-run this migration).

Safe to run more than once. Run once against the real dev DB:

    python -m apps.api.migrations.0007_users_email_unique
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "apps" / "api" / "roundzero.db"


def _index_exists(cur: sqlite3.Cursor, index_name: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    return cur.fetchone() is not None


def run(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"No DB at {db_path} - nothing to migrate (a fresh app start will create the full schema).")
        return

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    index_name = "ux_users_email"
    if _index_exists(cur, index_name):
        print("ux_users_email already present")
        con.close()
        return

    cur.execute("SELECT email, COUNT(*) c FROM users GROUP BY email HAVING c > 1")
    dupes = cur.fetchall()
    if dupes:
        con.close()
        raise SystemExit(
            f"Refusing to add the unique index - found {len(dupes)} duplicate email(s) still in the "
            f"users table: {[d[0] for d in dupes]}. Resolve those rows by hand first (see this file's "
            "docstring), then re-run this migration."
        )

    cur.execute("CREATE UNIQUE INDEX ux_users_email ON users (email)")
    con.commit()
    con.close()
    print("Added unique index ux_users_email on users.email")
    print("Migration complete.")


if __name__ == "__main__":
    run()
