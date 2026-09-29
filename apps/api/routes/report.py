"""
Cross-loop evaluation summary (/report on the frontend, IA-renamed to
/progress) - "a summarized view of evaluations along the link to each loop
interviews," plus the admin-curated action links Progress's "Next suggested
action" panel renders as 3 fixed subsections: substack_url ("Develop breadth
and depth"), class_url ("Develop core competency" - null until the class
actually exists, shown as "Coming soon"), and consultancy_booking_url ("Talk
to expert") - all three plain app_settings rows (apps/api/routes/admin.py).
weakest_dimensions/suggested_resources (StudyResource rows matched to the
candidate's weakest dimensions from their most recent evaluated round) are
still computed and returned here - the admin UI still curates them - but the
Progress page stopped rendering that list in favor of the 3 fixed
subsections above; kept in the response in case a future UI wants it rather
than deleting the feature outright. Entirely read-only, no LLM call -
everything here is either already-persisted EvaluationRecord data or
admin-curated content, so it works even while the interviewer/evaluator
providers are down (same reasoning as orchestrator.compare_rounds).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from apps.api import orchestrator
from apps.api.db import get_db
from apps.api.deps import get_current_user
from apps.api.models import AppSetting, RoundAttempt, StudyResource, User
from apps.api.schemas import HistoryItemOut

router = APIRouter(prefix="/v1/report", tags=["report"])

# How many of the candidate's weakest rubric dimensions to surface resources
# for - matches roundzero.debrief.synthesis.strengths_and_weaknesses' default
# top-N of 2, bumped to 3 here since "what to study next" wants a bit more
# breadth than a report headline does.
_N_WEAKEST = 3


class WeakDimensionOut(BaseModel):
    dimension: str
    label: str
    score: int


class SuggestedResourceOut(BaseModel):
    id: str
    dimension: str
    kind: str
    title: str
    url: str | None
    note: str | None


class ReportSummaryOut(BaseModel):
    total_loops: int
    total_rounds: int
    evaluated_rounds: int
    avg_readiness_pct: int | None
    latest_readiness_pct: int | None
    latest_hire_signal: str | None
    weakest_dimensions: list[WeakDimensionOut]
    suggested_resources: list[SuggestedResourceOut]
    consultancy_url: str | None
    substack_url: str | None
    class_url: str | None
    loops: list[HistoryItemOut]


@router.get("/summary", response_model=ReportSummaryOut)
def get_report_summary(
    user: User = Depends(get_current_user), db: DBSession = Depends(get_db)
) -> ReportSummaryOut:
    rounds = (
        db.query(RoundAttempt)
        .filter(RoundAttempt.user_id == user.id)
        .order_by(RoundAttempt.created_at.desc())
        .all()
    )
    loop_ids = {r.loop_attempt_id for r in rounds}
    history_items = [orchestrator.history_item_out(r, orchestrator.get_report(db, r.id)) for r in rounds]
    evaluated_items = [h for h in history_items if h.readiness_pct is not None]

    avg_readiness = (
        round(sum(h.readiness_pct for h in evaluated_items) / len(evaluated_items))
        if evaluated_items
        else None
    )

    weakest: list[WeakDimensionOut] = []
    suggested: list[SuggestedResourceOut] = []
    # RZ-02 (UI/UX review, 2026-09-29): skip not_assessed rounds when
    # looking for the "most recent evaluated round" to pull weakest
    # dimensions from - an empty round has an empty dimension_scores list
    # (nothing was scored), so picking it here would just silently show no
    # focus areas even though an earlier round has real, usable scores.
    latest_evaluation = None
    for r in rounds:
        if r.status != "EVALUATED":
            continue
        evaluation = orchestrator.get_report(db, r.id)
        if evaluation is not None and not evaluation.not_assessed:
            latest_evaluation = evaluation
            break
    if latest_evaluation is not None:
        # Same tie-break as roundzero.debrief.synthesis.strengths_and_weaknesses:
        # lowest score first, and among equal scores the higher-weight
        # (more critical) dimension counts as "weaker" for prioritization.
        ranked = sorted(latest_evaluation.dimension_scores, key=lambda d: (d.score, -d.weight))
        weakest = [
            WeakDimensionOut(dimension=d.dimension, label=d.label, score=d.score) for d in ranked[:_N_WEAKEST]
        ]
        weak_dims = {d.dimension for d in weakest}
        if weak_dims:
            rows = (
                db.query(StudyResource)
                .filter(StudyResource.dimension.in_(weak_dims))
                .order_by(StudyResource.dimension, StudyResource.sort_order)
                .all()
            )
            suggested = [
                SuggestedResourceOut(
                    id=r.id, dimension=r.dimension, kind=r.kind, title=r.title, url=r.url, note=r.note
                )
                for r in rows
            ]

    consultancy_setting = db.get(AppSetting, "consultancy_booking_url")
    substack_setting = db.get(AppSetting, "substack_url")
    class_setting = db.get(AppSetting, "class_url")

    return ReportSummaryOut(
        total_loops=len(loop_ids),
        total_rounds=len(rounds),
        evaluated_rounds=len(evaluated_items),
        avg_readiness_pct=avg_readiness,
        latest_readiness_pct=evaluated_items[0].readiness_pct if evaluated_items else None,
        latest_hire_signal=evaluated_items[0].hire_signal if evaluated_items else None,
        weakest_dimensions=weakest,
        suggested_resources=suggested,
        consultancy_url=consultancy_setting.value if consultancy_setting else None,
        substack_url=substack_setting.value if substack_setting else None,
        class_url=class_setting.value if class_setting else None,
        loops=history_items,
    )
