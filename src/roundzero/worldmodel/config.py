"""
Config loading for the world-model interviewer - competencies, the
dimension->competency map, the likelihood table, priors, prompts, and feature
flags. All content lives in rubrics/competencies/ and prompts/world_model/
(CLAUDE.md decision 2: configuration, not code).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPETENCIES_DIR = REPO_ROOT / "rubrics" / "competencies"
WM_PROMPTS_DIR = REPO_ROOT / "prompts" / "world_model"

POLARITIES = ("demonstrated", "absent", "contradicted")


@lru_cache(maxsize=None)
def load_competencies(version: str = "v1") -> dict:
    with (COMPETENCIES_DIR / f"{version}.yaml").open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def load_likelihoods(version: str = "v1") -> dict:
    with (COMPETENCIES_DIR / f"likelihoods_{version}.yaml").open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    _validate_table(data["default"], "default")
    for key, table in (data.get("overrides") or {}).items():
        _validate_table(table, key)
    return data


def _validate_table(table: dict, name: str) -> None:
    n_levels = len(level_keys())
    for polarity in POLARITIES:
        if len(table[polarity]) != n_levels:
            raise ValueError(f"likelihood table {name!r}: {polarity} needs {n_levels} values")
    for i in range(n_levels):
        total = sum(table[p][i] for p in POLARITIES)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"likelihood table {name!r}: level column {i} sums to {total}, not 1")


def level_keys() -> list[str]:
    return [lvl["key"] for lvl in load_competencies()["levels"]]


def level_label(index: int) -> str:
    return load_competencies()["levels"][index]["label"]


def competency_keys() -> list[str]:
    return [c["key"] for c in load_competencies()["competencies"]]


def competency(key: str) -> dict:
    for c in load_competencies()["competencies"]:
        if c["key"] == key:
            return c
    raise KeyError(key)


def dimension_to_competency(round_type: str, dimension: str) -> str | None:
    return (load_competencies()["dimension_map"].get(round_type) or {}).get(dimension)


def round_competencies(round_type: str) -> list[str]:
    """Competencies a round type can produce evidence for, in the canonical
    order of rubrics/competencies/v1.yaml."""
    mapped = {c for c in (load_competencies()["dimension_map"].get(round_type) or {}).values() if c}
    return [c for c in competency_keys() if c in mapped]


def likelihood_row(competency_key: str, polarity: str) -> list[float]:
    data = load_likelihoods()
    table = (data.get("overrides") or {}).get(competency_key) or data["default"]
    return list(table[polarity])


def prior_for(target_level: str | None) -> list[float]:
    priors = load_likelihoods()["priors"]
    return list(priors.get(target_level or "default") or priors["default"])


def update_setting(name: str) -> float:
    return float(load_likelihoods()["update"][name])


def diagnosis_setting(name: str) -> float:
    return float(load_likelihoods()["diagnosis"][name])


@lru_cache(maxsize=None)
def load_wm_prompt(name: str, version: str = "v1") -> str:
    """prompts/world_model/<name>/<version>.md with its YAML front matter
    stripped (the front matter is metadata for humans, PRD section 22 - the
    body is what the model sees)."""
    text = (WM_PROMPTS_DIR / name / f"{version}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    return text.strip()


# --- feature flags (specs/005 plan.md) ---------------------------------------

def wm_enabled() -> bool:
    return os.environ.get("ROUNDZERO_WM_ENABLED", "1") != "0"


def adaptive_mode() -> str:
    mode = os.environ.get("ROUNDZERO_WM_ADAPTIVE", "shadow").strip().lower()
    return mode if mode in ("off", "shadow", "live") else "shadow"


def flip_enabled() -> bool:
    return os.environ.get("ROUNDZERO_WM_FLIP", "1") != "0"


def sync_override() -> bool | None:
    raw = os.environ.get("ROUNDZERO_WM_SYNC")
    if raw is None or raw == "":
        return None
    return raw != "0"
