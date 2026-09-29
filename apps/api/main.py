"""
Round Zero API - FastAPI BFF. Milestones 1-3 scope: auth, round setup/interview
turn loop, evaluation/report, history. See
specs/001-ml-system-design-vertical-slice/milestone-{1,2,3}.md. Voice (Milestone
4) is not wired in here yet - LiveKit/STT/TTS integration is its own module
(src/roundzero/realtime/, per milestone-4.md) once that milestone starts.

Run from repo root (with the venv active):
    python -m uvicorn apps.api.main:app --reload --port 8000
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()  # picks up ANTHROPIC_API_KEY etc. from a repo-root .env, same as the CLI harness

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.db import Base, SessionLocal, engine
from apps.api.routes import admin, auth, billing, config, feedback, loops, prep_plans, profile, real_interviews, report, rounds, world_model
from apps.api.seed import seed_defaults

Base.metadata.create_all(bind=engine)

# One-time bootstrap of the Setup form's lookup tables (role/level/domain/
# company/duration options) - see apps/api/seed.py's docstring for why a
# seed step still exists even though these are now real DB tables, not
# hardcoded Python lists. Idempotent - only inserts into a table that's
# still empty, so this is safe to run on every startup.
with SessionLocal() as _seed_db:
    seed_defaults(_seed_db)

app = FastAPI(title="Round Zero API")

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "https://roundzero.architectingintelligencelabs.com",
]
_cors_env = os.environ.get("CORS_ORIGINS", "").strip()
_cors_origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else _DEFAULT_CORS_ORIGINS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://roundzero-.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(config.router)
app.include_router(profile.router)
app.include_router(rounds.router)
app.include_router(report.router)
app.include_router(admin.router)
app.include_router(loops.router)
app.include_router(real_interviews.router)
app.include_router(prep_plans.router)
app.include_router(feedback.router)
app.include_router(world_model.router)
app.include_router(world_model.trend_router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "interviewer_llm": _llm_mode(),
        "evaluator_llm": "gpt-5-mini" if os.environ.get("OPENAI_API_KEY") else "rule-based",
    }


def _llm_mode() -> str:
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini-3.6-flash"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic (legacy, not the locked V1 default)"
    return "mock"
