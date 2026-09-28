"""
SQLAlchemy engine/session setup. Uses SQLite by default (apps/api/roundzero.db) -
no Postgres install required to get milestone 1 running. Swap by setting
DATABASE_URL to a Postgres DSN; nothing above this module needs to change,
per CLAUDE.md's storage/ repository-abstraction principle.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = REPO_ROOT / "apps" / "api" / "roundzero.db"
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{DEFAULT_SQLITE_PATH}"
# `or`, not get()'s default arg - .env.example ships DATABASE_URL= (empty, not
# unset) so local dev without Supabase still falls back to SQLite instead of
# SQLAlchemy choking on an empty connection string.

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
