"""
Idempotent startup seed for the Setup form's lookup tables (RoleFamilyOption /
LevelOption / DomainOption / CompanyProfileOption / DurationOption,
apps/api/models.py) - these are real, queryable, DB-editable tables now, not
hardcoded Python lists baked into apps/api/routes/config.py. A seed step still
exists because a brand-new database has to start with *something* sensible or
the Setup page would render empty dropdowns on first boot - that's a one-time
bootstrap of default reference data, the same role every app's seed/fixture
step plays, not a re-hardcoding of the same problem. seed_defaults() only ever
inserts rows into a table that is completely empty, so it never overwrites
anything an operator has since edited directly in the DB, and it's safe to
call on every app startup (apps/api/main.py).

Deliberately NOT converted to DB tables by this same pass: prompts/ and
rubrics/ (CLAUDE.md decision 2 - versioned Markdown/YAML on purpose, so a
prompt or rubric change has a diff, a reviewer, and a version string an
EvaluationRecord can point back to) and evaluator.py's HIRE_SIGNAL_THRESHOLDS
(core scoring logic covered by evals/golden/ml_system_design's regression
suite - moving it into an unreviewed, untested DB table would undermine the
exact guarantee that suite exists to provide). Those are deliberate
configuration-as-code, not the kind of hardcoding this pass is about.
"""
from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from apps.api.models import (
    CompanyProfileOption,
    DomainOption,
    DurationOption,
    LevelOption,
    RoleFamilyOption,
    RoundTypeOption,
)

# value fields must keep matching the slugs
# roundzero.interviewers.ml_system_design.agent.pick_scenario and
# prompts/interviewers/ml_system_design/scenarios.yaml already use - see each
# model's docstring in apps/api/models.py.
_ROLE_FAMILIES = [
    ("ml_engineer", "ML Engineer"),
    ("ml_infra_engineer", "ML Infra Engineer"),
    ("applied_scientist", "Applied Scientist"),
    ("research_scientist", "Research Scientist"),
    ("data_scientist", "Data Scientist"),
    ("backend_engineer", "Backend Engineer"),
    ("engineering_manager", "Engineering Manager"),
]
_LEVELS = [
    ("entry_level", "Entry Level (0-2 yrs)"),
    ("mid_level", "Mid-Level (2-5 yrs)"),
    ("senior", "Senior (5-8 yrs)"),
    ("staff", "Staff (cross-team leadership)"),
    ("principal", "Principal (org-wide leadership)"),
    ("not_sure", "Not sure"),
]
# entry_level/mid_level/not_sure are UI-only today: no scenario bank has
# entries tagged with these levels (prompts/interviewers/*/scenarios.yaml
# only use senior/staff/principal), and every evaluator prompt is hardcoded
# to a fixed Staff/Principal-caliber bar regardless of the level picked
# (src/roundzero/leveling/calibration.py's docstring). Each interviewer's
# pick_scenario() progressively relaxes its level filter down to the full
# scenario list rather than ever failing, so picking one of these three
# doesn't error - it just serves the same undifferentiated Senior+ content,
# which the Setup page discloses inline when one of these is selected.
_DOMAINS = [
    ("ml_infra", "ML Infrastructure"),
    ("general_ml", "General ML"),
    ("llm_genai", "LLM / Gen AI"),
    ("computer_vision", "Computer Vision"),
    ("autonomous_vehicle", "Autonomous Vehicle"),
    # Added for ml_depth's Reinforcement Learning sub-area (2026-09-03) - see
    # prompts/interviewers/ml_depth/scenarios.yaml's reinforcement_learning-
    # tagged scenarios. Existing round types that don't tag any scenario with
    # this domain simply never match it - no effect on them.
    ("reinforcement_learning", "Reinforcement Learning"),
]
_COMPANIES = [
    ("generic", "Generic"),
    ("big_tech", "Big Tech"),
    ("startup", "Startup"),
]
_DURATIONS = [45, 60]

# Matches configs/loops/principal_ml_infra.yaml's round list. `enabled` here
# tracks whether a real interviewer exists (src/roundzero/interviewers/) - as
# of 2026-09-05 that's every round type except hiring_manager (see
# RoundTypeOption's docstring in apps/api/models.py for what `enabled` does
# and doesn't control for them - this seed value alone doesn't gate Setup,
# apps/web/lib/roundTypes.ts's own `available` flag does that today).
_ROUND_TYPES = [
    ("ml_system_design", "ML System Design", True),
    ("coding", "Coding", True),
    ("backend_system_design", "Backend System Design", True),
    ("ml_depth", "ML Depth", True),
    ("technical_leadership", "Technical Leadership", True),
    ("xfn", "Cross-functional", True),
    ("hiring_manager", "Hiring Manager", False),
]


def seed_defaults(db: DBSession) -> None:
    if db.query(RoleFamilyOption).count() == 0:
        db.add_all(
            RoleFamilyOption(value=value, label=label, sort_order=i)
            for i, (value, label) in enumerate(_ROLE_FAMILIES)
        )
    if db.query(LevelOption).count() == 0:
        db.add_all(LevelOption(value=value, label=label, sort_order=i) for i, (value, label) in enumerate(_LEVELS))
    if db.query(DomainOption).count() == 0:
        db.add_all(DomainOption(value=value, label=label, sort_order=i) for i, (value, label) in enumerate(_DOMAINS))
    if db.query(CompanyProfileOption).count() == 0:
        db.add_all(
            CompanyProfileOption(value=value, label=label, sort_order=i)
            for i, (value, label) in enumerate(_COMPANIES)
        )
    if db.query(DurationOption).count() == 0:
        db.add_all(DurationOption(minutes=minutes, sort_order=i) for i, minutes in enumerate(_DURATIONS))
    if db.query(RoundTypeOption).count() == 0:
        db.add_all(
            RoundTypeOption(value=value, label=label, enabled=enabled, sort_order=i)
            for i, (value, label, enabled) in enumerate(_ROUND_TYPES)
        )
    db.commit()
