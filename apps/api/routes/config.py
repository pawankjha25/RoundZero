"""
Dropdown options for the candidate setup form - plan.md: "Single simple form,
no wizard." Backed by real DB tables (RoleFamilyOption / LevelOption /
DomainOption / CompanyProfileOption / DurationOption, apps/api/models.py),
seeded with sensible defaults on startup (apps/api/seed.py) rather than
hardcoded in this route handler - an operator can add/relabel/reorder options
directly in the DB without a code deploy. The `value` fields still must match
the slugs roundzero.interviewers.ml_system_design.agent.pick_scenario and
prompts/interviewers/ml_system_design/scenarios.yaml already use (level:
senior/staff/principal, domain: ml_infra/general_ml) - moving the list into
the DB doesn't remove that coupling, it just means it's no longer enforced by
literally being the same Python list in both places.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from apps.api.db import get_db
from apps.api.models import (
    CompanyProfileOption,
    DomainOption,
    DurationOption,
    LevelOption,
    RoleFamilyOption,
    RoundTypeOption,
)
from apps.api.schemas import CompanyOptionOut, OptionOut, OptionsOut, RoundTypeOptionOut

router = APIRouter(prefix="/v1/config", tags=["config"])


@router.get("/options", response_model=OptionsOut)
def get_options(db: DBSession = Depends(get_db)) -> OptionsOut:
    return OptionsOut(
        role_families=[
            OptionOut(value=r.value, label=r.label)
            for r in db.query(RoleFamilyOption).order_by(RoleFamilyOption.sort_order).all()
        ],
        levels=[
            OptionOut(value=r.value, label=r.label)
            for r in db.query(LevelOption).order_by(LevelOption.sort_order).all()
        ],
        domains=[
            OptionOut(value=r.value, label=r.label)
            for r in db.query(DomainOption).order_by(DomainOption.sort_order).all()
        ],
        companies=[
            CompanyOptionOut(value=r.value, label=r.label, tier=r.tier)
            for r in db.query(CompanyProfileOption).order_by(CompanyProfileOption.sort_order).all()
        ],
        duration_minutes=[r.minutes for r in db.query(DurationOption).order_by(DurationOption.sort_order).all()],
        round_types=[
            RoundTypeOptionOut(value=r.value, label=r.label, enabled=r.enabled)
            for r in db.query(RoundTypeOption).order_by(RoundTypeOption.sort_order).all()
        ],
    )
