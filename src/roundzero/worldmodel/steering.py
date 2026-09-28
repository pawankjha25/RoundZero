"""
Live-mode steering (specs/005): turns the picker's chosen option into the
internal probe note appended to the interviewer's per-turn message. Template in
prompts/world_model/probe_hint/v1.md (CLAUDE.md: no prompt text in Python).
The note never contains a level estimate - the level is only ever shown in the
post-interview report (decided 2026-09-28).
"""
from __future__ import annotations

from roundzero.worldmodel import config
from roundzero.worldmodel.models import FollowUpOption


def render_probe_hint(option: FollowUpOption | None) -> str | None:
    if option is None:
        return None
    meta = config.competency(option.competency)
    return config.load_wm_prompt("probe_hint").format(
        competency=meta["label"],
        intent=meta["probe_intent"].rstrip(".").lower(),
        bar=meta["staff_vs_senior"].rstrip(".").lower(),
    )


def probe_block(probe_hint: str | None) -> str:
    """What each interviewer agent appends to its user message - empty unless
    live mode produced a hint."""
    return f"\n{probe_hint}\n" if probe_hint else ""
