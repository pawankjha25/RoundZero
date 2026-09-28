"""
Versioned rubric loader - never hardcode dimension weights/labels in evaluation
code, per CLAUDE.md working conventions. Mirrors the pattern in
roundzero.llm.prompt_loader.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
RUBRICS_DIR = REPO_ROOT / "rubrics"


@lru_cache(maxsize=None)
def load_rubric(round_type: str, version: str = "v1") -> dict:
    path = RUBRICS_DIR / round_type / f"{version}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No rubric at {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def rubric_dimension_keys(round_type: str, version: str = "v1") -> list[str]:
    """Dimension keys only, in rubric-file order - single source of truth for
    a round's coverage-tracking shape (apps/api/orchestrator.py's
    ConversationState.coverage starts every round with one of these per
    dimension, all NOT_COVERED), so it can never drift from the rubric file
    itself the way a separately-hardcoded Python list could."""
    return [d["key"] for d in load_rubric(round_type, version)["dimensions"]]
