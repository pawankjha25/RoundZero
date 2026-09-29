"""
Admin-only management routes. Every route here requires get_current_admin
(apps/api/deps.py's ADMIN_EMAILS allowlist), enforced at the dependency
level so a hidden/removed frontend nav link is never the only thing standing
between a non-admin and these endpoints.

Covers exactly what the "don't hardcode anything, give me an admin view"
pass asked for: the Setup form's dropdown option tables (role/level/domain/
company/duration - apps/api/routes/config.py now reads these instead of a
hardcoded list), which round types show as available vs "coming soon"
(RoundTypeOption - see that model's docstring in apps/api/models.py for what
`enabled` does and doesn't unlock), the study resources that power
/report's "Next suggested action" (StudyResource - deliberately unseeded),
and the one global setting candidates see (the consultancy booking URL,
read back by apps/api/routes/report.py).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from apps.api import orchestrator
from apps.api.db import get_db
from apps.api.deps import get_current_admin
from apps.api.models import (
    AppSetting,
    CompanyProfileOption,
    DomainOption,
    DurationOption,
    Feedback,
    LevelOption,
    RoleFamilyOption,
    RoundTypeOption,
    StudyResource,
    User,
    UserEntitlement,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


# --- Generic value/label option lists (role families, levels, domains, companies) ---
# Editing `value` itself is deliberately not supported (only label/sort_order) -
# `value` is what's already stored on historical RoundAttempt rows
# (role_family/level/domain/company_profile columns are plain strings, not
# foreign keys), so renaming it out from under existing data would silently
# orphan those rows' meaning. Deleting a row is fine - it just stops
# appearing in the dropdown; rows referencing it keep displaying their stored
# value as-is (apps/web's formatLabel() slug-title-cases whatever it gets).

_OPTION_MODELS: dict[str, type] = {
    "role-families": RoleFamilyOption,
    "levels": LevelOption,
    "domains": DomainOption,
    "companies": CompanyProfileOption,
}


class OptionRowOut(BaseModel):
    value: str
    label: str
    sort_order: int
    # Only ever set for kind == "companies" (CompanyProfileOption.tier) -
    # None for every other option kind, which have no such column. See that
    # model's docstring in apps/api/models.py for what tier is (cosmetic
    # interview-complexity grouping) and isn't (no interview-behavior change).
    tier: str | None = None


class OptionRowIn(BaseModel):
    value: str
    label: str
    sort_order: int = 0
    tier: str | None = None


class OptionRowUpdate(BaseModel):
    label: str | None = None
    sort_order: int | None = None
    tier: str | None = None


def _option_model(kind: str) -> type:
    model = _OPTION_MODELS.get(kind)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown option list: {kind}")
    return model


def _option_row_out(row) -> OptionRowOut:
    return OptionRowOut(
        value=row.value,
        label=row.label,
        sort_order=row.sort_order,
        tier=getattr(row, "tier", None),
    )


@router.get("/options/{kind}", response_model=list[OptionRowOut])
def list_options(kind: str, db: DBSession = Depends(get_db)) -> list[OptionRowOut]:
    model = _option_model(kind)
    rows = db.query(model).order_by(model.sort_order).all()
    return [_option_row_out(r) for r in rows]


@router.post("/options/{kind}", response_model=OptionRowOut)
def create_option(kind: str, payload: OptionRowIn, db: DBSession = Depends(get_db)) -> OptionRowOut:
    model = _option_model(kind)
    if db.get(model, payload.value) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"'{payload.value}' already exists in {kind}")
    row = model(value=payload.value, label=payload.label, sort_order=payload.sort_order)
    if payload.tier is not None and hasattr(row, "tier"):
        row.tier = payload.tier
    db.add(row)
    db.commit()
    return _option_row_out(row)


@router.put("/options/{kind}/{value}", response_model=OptionRowOut)
def update_option(
    kind: str, value: str, payload: OptionRowUpdate, db: DBSession = Depends(get_db)
) -> OptionRowOut:
    model = _option_model(kind)
    row = db.get(model, value)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"'{value}' not found in {kind}")
    if payload.label is not None:
        row.label = payload.label
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    if payload.tier is not None and hasattr(row, "tier"):
        row.tier = payload.tier
    db.commit()
    return _option_row_out(row)


@router.delete("/options/{kind}/{value}", status_code=status.HTTP_204_NO_CONTENT)
def delete_option(kind: str, value: str, db: DBSession = Depends(get_db)) -> None:
    model = _option_model(kind)
    row = db.get(model, value)
    if row is not None:
        db.delete(row)
        db.commit()


# --- Durations (minutes IS the value, there's no separate label) ---


class DurationOut(BaseModel):
    minutes: int
    sort_order: int


class DurationIn(BaseModel):
    minutes: int
    sort_order: int = 0


@router.get("/durations", response_model=list[DurationOut])
def list_durations(db: DBSession = Depends(get_db)) -> list[DurationOut]:
    rows = db.query(DurationOption).order_by(DurationOption.sort_order).all()
    return [DurationOut(minutes=r.minutes, sort_order=r.sort_order) for r in rows]


@router.post("/durations", response_model=DurationOut)
def create_duration(payload: DurationIn, db: DBSession = Depends(get_db)) -> DurationOut:
    if db.get(DurationOption, payload.minutes) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"{payload.minutes} minutes already exists")
    row = DurationOption(minutes=payload.minutes, sort_order=payload.sort_order)
    db.add(row)
    db.commit()
    return DurationOut(minutes=row.minutes, sort_order=row.sort_order)


@router.delete("/durations/{minutes}", status_code=status.HTTP_204_NO_CONTENT)
def delete_duration(minutes: int, db: DBSession = Depends(get_db)) -> None:
    row = db.get(DurationOption, minutes)
    if row is not None:
        db.delete(row)
        db.commit()


# --- Round types ---


class RoundTypeAdminOut(BaseModel):
    value: str
    label: str
    enabled: bool
    sort_order: int


class RoundTypeUpdate(BaseModel):
    label: str | None = None
    enabled: bool | None = None
    sort_order: int | None = None


@router.get("/round-types", response_model=list[RoundTypeAdminOut])
def list_round_types(db: DBSession = Depends(get_db)) -> list[RoundTypeAdminOut]:
    rows = db.query(RoundTypeOption).order_by(RoundTypeOption.sort_order).all()
    return [
        RoundTypeAdminOut(value=r.value, label=r.label, enabled=r.enabled, sort_order=r.sort_order) for r in rows
    ]


@router.put("/round-types/{value}", response_model=RoundTypeAdminOut)
def update_round_type(
    value: str, payload: RoundTypeUpdate, db: DBSession = Depends(get_db)
) -> RoundTypeAdminOut:
    row = db.get(RoundTypeOption, value)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"'{value}' not found")
    if payload.label is not None:
        row.label = payload.label
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    db.commit()
    return RoundTypeAdminOut(value=row.value, label=row.label, enabled=row.enabled, sort_order=row.sort_order)


# --- Study resources ("Next suggested action" content on /report) ---


class StudyResourceOut(BaseModel):
    id: str
    dimension: str
    round_type: str
    kind: str
    title: str
    url: str | None
    note: str | None
    sort_order: int


class StudyResourceIn(BaseModel):
    dimension: str
    round_type: str = "ml_system_design"
    kind: str = "link"
    title: str
    url: str | None = None
    note: str | None = None
    sort_order: int = 0


class StudyResourceUpdate(BaseModel):
    dimension: str | None = None
    kind: str | None = None
    title: str | None = None
    url: str | None = None
    note: str | None = None
    sort_order: int | None = None


def _resource_out(r: StudyResource) -> StudyResourceOut:
    return StudyResourceOut(
        id=r.id,
        dimension=r.dimension,
        round_type=r.round_type,
        kind=r.kind,
        title=r.title,
        url=r.url,
        note=r.note,
        sort_order=r.sort_order,
    )


@router.get("/study-resources", response_model=list[StudyResourceOut])
def list_study_resources(db: DBSession = Depends(get_db)) -> list[StudyResourceOut]:
    rows = db.query(StudyResource).order_by(StudyResource.dimension, StudyResource.sort_order).all()
    return [_resource_out(r) for r in rows]


@router.post("/study-resources", response_model=StudyResourceOut)
def create_study_resource(payload: StudyResourceIn, db: DBSession = Depends(get_db)) -> StudyResourceOut:
    row = StudyResource(
        dimension=payload.dimension,
        round_type=payload.round_type,
        kind=payload.kind,
        title=payload.title,
        url=payload.url,
        note=payload.note,
        sort_order=payload.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _resource_out(row)


@router.put("/study-resources/{resource_id}", response_model=StudyResourceOut)
def update_study_resource(
    resource_id: str, payload: StudyResourceUpdate, db: DBSession = Depends(get_db)
) -> StudyResourceOut:
    row = db.get(StudyResource, resource_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resource not found")
    for field in ("dimension", "kind", "title", "url", "note", "sort_order"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    db.commit()
    return _resource_out(row)


@router.delete("/study-resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study_resource(resource_id: str, db: DBSession = Depends(get_db)) -> None:
    row = db.get(StudyResource, resource_id)
    if row is not None:
        db.delete(row)
        db.commit()


# --- Settings (currently just the consultancy booking URL) ---

# Extended (2026-09) alongside Progress page's "Next suggested action" redesign into 3 fixed subsections - substack_url (breadth/depth reading) and class_url (the not-yet-live course link, left null until it exists) sit alongside the original consultancy link, same admin-curated pattern.
_KNOWN_SETTING_KEYS = {"consultancy_booking_url", "substack_url", "class_url"}


class AppSettingOut(BaseModel):
    key: str
    value: str | None


class AppSettingUpdate(BaseModel):
    value: str | None = None


@router.get("/settings", response_model=list[AppSettingOut])
def list_settings(db: DBSession = Depends(get_db)) -> list[AppSettingOut]:
    stored = {r.key: r.value for r in db.query(AppSetting).all()}
    return [AppSettingOut(key=k, value=stored.get(k)) for k in sorted(_KNOWN_SETTING_KEYS)]


@router.put("/settings/{key}", response_model=AppSettingOut)
def update_setting(key: str, payload: AppSettingUpdate, db: DBSession = Depends(get_db)) -> AppSettingOut:
    if key not in _KNOWN_SETTING_KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown setting: {key}")
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key)
        db.add(row)
    row.value = payload.value
    db.commit()
    return AppSettingOut(key=key, value=row.value)


# --- Feedback (read-only list of what pilot testers submitted via the
# floating widget - apps/web/components/FeedbackWidget.tsx / apps/api/
# routes/feedback.py). No update/delete route - nothing here is meant to be
# edited, just read. ---


class FeedbackAdminOut(BaseModel):
    id: str
    user_email: str
    user_name: str
    kind: str
    message: str
    page_path: str | None
    created_at: datetime


@router.get("/feedback", response_model=list[FeedbackAdminOut])
def list_feedback(db: DBSession = Depends(get_db)) -> list[FeedbackAdminOut]:
    rows = (
        db.query(Feedback, User)
        .join(User, Feedback.user_id == User.id)
        .order_by(Feedback.created_at.desc())
        .all()
    )
    return [
        FeedbackAdminOut(
            id=f.id,
            user_email=u.email,
            user_name=u.name,
            kind=f.kind,
            message=f.message,
            page_path=f.page_path,
            created_at=f.created_at,
        )
        for f, u in rows
    ]



# --- Users (entitlement/quota administration - Phase 1 of the pricing
# rollout, claude.ai Project "roundzero" > pricing-design.md: no Stripe yet,
# an admin grants/adjusts entitlements by hand. Every user always has exactly
# one UserEntitlement row (auto-created on first sight - apps/api/deps.py::
# get_current_user), so this is a straightforward list + patch, same shape as
# the option-list CRUD above. ---


class UserAdminOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime
    cohort: str
    plan: str
    billing_interval: str
    rounds_included: int
    rounds_used: int
    rounds_remaining: int
    current_period_start: datetime
    expires_at: datetime | None
    is_expired: bool


class EntitlementUpdateIn(BaseModel):
    # Every field optional and independently applied - an admin call only
    # ever touches what it explicitly sets, same "only apply what's not
    # None" convention as OptionRowUpdate/StudyResourceUpdate above.
    cohort: str | None = None  # "tester" | "normal" | "paid"
    plan: str | None = None  # "none" | "monthly" | "yearly" | "founding" | "payperloop"
    billing_interval: str | None = None  # "none" | "monthly" | "yearly" | "one_time"
    rounds_included: int | None = None  # absolute set
    add_rounds: int | None = None  # increment rounds_included by this many instead of setting it outright
    reset_period: bool = False  # also bump current_period_start to now, so rounds_used starts counting fresh
    clear_expiry: bool = False  # explicit flag, since expires_at=null in the body is ambiguous with "not sent"
    expires_at: datetime | None = None  # only applied when clear_expiry is False


def _get_or_create_entitlement(db: DBSession, user_id: str) -> UserEntitlement:
    row = db.query(UserEntitlement).filter(UserEntitlement.user_id == user_id).first()
    if row is None:
        # Backfill path for a user created before this feature shipped who
        # hasn't made an authenticated request since (apps/api/deps.py::
        # get_current_user would otherwise be what creates this row) - an
        # admin shouldn't have to wait for that to grant them something.
        row = UserEntitlement(user_id=user_id, cohort="normal", plan="none", rounds_included=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _user_admin_out(db: DBSession, user: User) -> UserAdminOut:
    status_ = orchestrator.get_entitlement_status(db, user.id)
    return UserAdminOut(
        id=user.id,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
        cohort=status_.cohort,
        plan=status_.plan,
        billing_interval=status_.billing_interval,
        rounds_included=status_.rounds_included,
        rounds_used=status_.rounds_used,
        rounds_remaining=status_.rounds_remaining,
        current_period_start=status_.current_period_start,
        expires_at=status_.expires_at,
        is_expired=status_.is_expired,
    )


@router.get("/users", response_model=list[UserAdminOut])
def list_users(db: DBSession = Depends(get_db)) -> list[UserAdminOut]:
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_user_admin_out(db, u) for u in users]


@router.patch("/users/{user_id}/entitlement", response_model=UserAdminOut)
def update_user_entitlement(user_id: str, payload: EntitlementUpdateIn, db: DBSession = Depends(get_db)) -> UserAdminOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    entitlement = _get_or_create_entitlement(db, user_id)

    if payload.cohort is not None:
        entitlement.cohort = payload.cohort
    if payload.plan is not None:
        entitlement.plan = payload.plan
    if payload.billing_interval is not None:
        entitlement.billing_interval = payload.billing_interval
    if payload.rounds_included is not None:
        entitlement.rounds_included = payload.rounds_included
    if payload.add_rounds is not None:
        entitlement.rounds_included = entitlement.rounds_included + payload.add_rounds
    if payload.reset_period:
        entitlement.current_period_start = datetime.now(timezone.utc)
    if payload.clear_expiry:
        entitlement.expires_at = None
    elif payload.expires_at is not None:
        entitlement.expires_at = payload.expires_at

    db.commit()
    db.refresh(user)
    return _user_admin_out(db, user)
