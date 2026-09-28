"""
Session-wide safety net for tests/unit's SQLite tests.

apps.api.db configures its `engine`/`SessionLocal` once, at the FIRST import
of that module anywhere in the pytest process (plain Python module caching -
see the module's own docstring). Whichever test file pytest happens to
collect first "wins" that binding for every other file that later does
`from apps.api.db import engine` - and if nothing has set DATABASE_URL by
then, that first import silently binds the shared engine to the real
development database (apps/api/roundzero.db), not a throwaway file. Every
later test file's own `os.environ["DATABASE_URL"] = ...` line runs too late
to matter, since the module (and its already-created `engine`) is already
cached.

This bit the real dev db once already: adding a new test file that imported
apps.api.db before setting DATABASE_URL made it the "first importer", so
every old-pattern test file that runs after it wrote real rows into
apps/api/roundzero.db instead of its own isolated tempfile - and on this
repo's bridged/mounted filesystem, concurrent SQLite writers there also
triggered persistent "disk I/O error"s until the file was manually repaired.

Fixing every individual test file to always self-order its own import is
fragile (it's exactly what broke). Instead, this conftest.py runs before
pytest imports ANY test module in this directory and pins a session-wide
tempfile DATABASE_URL up front, so apps.api.db can never fall back to the
real dev db during a test run - no matter which file gets collected first,
and even for test files that don't think about isolation at all.

Individual test files are still free to layer their own fully-private
`create_engine(...)` (the pattern in test_config_options.py and
test_admin_and_report.py) for real per-file isolation from each other; this
conftest is only the last-resort guardrail against ever touching the real
database file.
"""
from __future__ import annotations

import os
import tempfile

if not os.environ.get("DATABASE_URL"):
    _fd, _path = tempfile.mkstemp(suffix=".db", prefix="roundzero_pytest_default_")
    os.close(_fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{_path}"
