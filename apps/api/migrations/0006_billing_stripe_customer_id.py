"""
One-off migration for Phase 2 (Stripe Pay-per-loop Checkout - see
claude/pricing-design.md in the roundzero project).

Same rationale as every prior numbered migration here: Base.metadata.
create_all() only ever CREATEs new tables, never ALTERs an existing one.
stripe_webhook_events is a brand new table, so create_all() picked it up
fine on server startup - but users already existed, so its new
stripe_customer_id column needs a manual ALTER TABLE before the app is
restarted with the updated models.py, or every query touching User (which
is most authenticated requests, via apps/api/deps.py::get_current_user)
breaks with "no such column: users.stripe_customer_id" (seen live: this is
what put a real local dev instance in a redirect-to-/login loop, since the
frontend's root page and every AppShell-wrapped page call GET /v1/auth/me,
which 500s without this column, and the frontend's catch-all sends any
failed me() call back to /login).

No backfill needed - stripe_customer_id is nullable and every existing user
(who by definition hasn't bought anything via Stripe yet) is correctly left
NULL; it gets backfilled the first time that user's Checkout webhook fires
(apps/api/routes/billing.py::stripe_webhook).

Safe to run more than once. Run once against the real dev DB:

    python -m apps.api.migrations.0006_billing_stripe_customer_id
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

    if not _column_exists(cur, "users", "stripe_customer_id"):
        cur.execute("ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_users_stripe_customer_id "
            "ON users (stripe_customer_id)"
        )
        print("Added users.stripe_customer_id (+ index)")
    else:
        print("users.stripe_customer_id already present")

    con.commit()
    con.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()
