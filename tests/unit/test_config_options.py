"""
Setup form's dropdown options (role/level/domain/company/duration) moved from
hardcoded Python lists in apps/api/routes/config.py to real DB tables
(RoleFamilyOption/LevelOption/DomainOption/CompanyProfileOption/
DurationOption, apps/api/models.py) seeded on startup (apps/api/seed.py).
This proves three things a hardcoded list can't: (1) the DB is what the
endpoint actually reads (edit a row, the endpoint reflects it), (2) seeding
is idempotent - never duplicates or clobbers rows on repeated app startups,
and (3) a fresh, unseeded DB still resolves to sensible defaults, matching
what apps/api/routes/config.py used to return before this change.

Uses its own private SQLite engine + a get_db dependency override, rather
than the "set DATABASE_URL before importing apps.api.db" pattern the older
tests in this directory use (test_orchestrator_interviewer_unavailable.py,
test_round_comparison.py): apps.api.db.engine/SessionLocal are module-level
singletons configured once at the FIRST import of apps.api.db anywhere in
the pytest process, so whichever test file pytest happens to collect first
"wins" that DATABASE_URL for every other file too - a real bug this file hit
once (see git history) when a new, alphabetically-earlier test file raced it.
Overriding get_db per-app sidesteps that race entirely: this file's tables
live in their own throwaway SQLite file no matter what any other test file
does or which order pytest collects things in. Also avoids importing
apps.api.main directly for the same reason test_admin_and_report.py does
(its module-level load_dotenv() would leak real provider API keys into every
test file collected after this one).
"""
from __future__ import annotations

import tempfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.db import Base, get_db
from apps.api.models import CompanyProfileOption, RoleFamilyOption
from apps.api.routes import config
from apps.api.seed import seed_defaults

_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
SessionLocal = sessionmaker(bind=_engine)

with SessionLocal() as _seed_db:
    seed_defaults(_seed_db)

_app = FastAPI()
_app.include_router(config.router)


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_app.dependency_overrides[get_db] = _override_get_db
client = TestClient(_app)


def test_options_endpoint_matches_the_old_hardcoded_defaults():
    r = client.get("/v1/config/options")
    assert r.status_code == 200
    body = r.json()
    assert [o["value"] for o in body["role_families"]] == ["ml_engineer", "ml_infra_engineer", "applied_scientist"]
    assert [o["value"] for o in body["levels"]] == ["senior", "staff", "principal"]
    assert [o["value"] for o in body["domains"]] == ["ml_infra", "general_ml"]
    assert [o["value"] for o in body["companies"]] == ["generic", "big_tech", "startup"]
    assert body["duration_minutes"] == [45, 60]


def test_seeding_is_idempotent_and_never_duplicates_rows():
    db = SessionLocal()
    before = db.query(RoleFamilyOption).count()
    seed_defaults(db)
    seed_defaults(db)
    seed_defaults(db)
    after = db.query(RoleFamilyOption).count()
    db.close()
    assert before == after == 3


def test_editing_a_row_in_the_db_changes_what_the_endpoint_returns():
    # This is the whole point of moving off a hardcoded list - proves the
    # endpoint is a live read of the table, not a cached/static value.
    db = SessionLocal()
    row = db.get(CompanyProfileOption, "startup")
    original_label = row.label
    row.label = "Early-Stage Startup"
    db.commit()
    db.close()

    r = client.get("/v1/config/options")
    companies = {o["value"]: o["label"] for o in r.json()["companies"]}
    assert companies["startup"] == "Early-Stage Startup"

    # Restore, so this test doesn't leak state into whichever test runs next
    # against this file's SQLite file.
    db = SessionLocal()
    row = db.get(CompanyProfileOption, "startup")
    row.label = original_label
    db.commit()
    db.close()


def test_seed_defaults_on_a_completely_fresh_empty_db_produces_the_same_options():
    fresh_engine = create_engine(f"sqlite:///{tempfile.mkstemp(suffix='.db')[1]}")
    Base.metadata.create_all(bind=fresh_engine)
    FreshSession = sessionmaker(bind=fresh_engine)
    db = FreshSession()
    assert db.query(RoleFamilyOption).count() == 0
    seed_defaults(db)
    assert [r.value for r in db.query(RoleFamilyOption).order_by(RoleFamilyOption.sort_order)] == [
        "ml_engineer",
        "ml_infra_engineer",
        "applied_scientist",
    ]
    db.close()
