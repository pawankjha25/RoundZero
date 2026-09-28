"""
Versioned prompt/scenario loader. Prompts and scenarios are content, not code - see
CLAUDE.md decision 2 and docs/PRD.md section 22 ("no prompts embedded directly in
route handlers"). Nothing in roundzero/ should hold prompt text as a Python string;
it is always loaded from prompts/ by category + round type + version.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

# src/roundzero/llm/prompt_loader.py -> repo root is 4 parents up.
REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"


@lru_cache(maxsize=32)
def load_named_prompt(category: str, round_type: str, version: str = "v1") -> str:
    """category: 'interviewers', 'evaluators', or 'report' - see prompts/ layout."""
    path = PROMPTS_DIR / category / round_type / f"{version}.md"
    return path.read_text()


def load_prompt(round_type: str, version: str = "v1") -> str:
    return load_named_prompt("interviewers", round_type, version)


def load_evaluator_prompt(round_type: str, version: str = "v1") -> str:
    return load_named_prompt("evaluators", round_type, version)


def load_report_prompt(round_type: str, version: str = "v1") -> str:
    return load_named_prompt("report", round_type, version)


def load_committee_prompt(version: str = "v1") -> str:
    """Virtual Hiring Committee synthesis prompt (specs/002-full-loop-platform
    P0.6) - no round_type axis, since it synthesizes across round types within
    one loop rather than scoring one round type. Lives directly under
    prompts/committee/, not nested per-round-type like load_report_prompt."""
    path = PROMPTS_DIR / "committee" / f"{version}.md"
    return path.read_text()


@lru_cache(maxsize=32)
def load_scenarios(round_type: str) -> tuple[dict, ...]:
    path = PROMPTS_DIR / "interviewers" / round_type / "scenarios.yaml"
    data = yaml.safe_load(path.read_text())
    return tuple(data["scenarios"])


def load_real_interview_prompt(version: str = "v1") -> str:
    """Real Interview Experience structuring prompt (specs/002-full-loop-platform
    P0.11) - no round_type axis, same "lives directly under its own top-level
    prompts/ folder" shape as load_committee_prompt."""
    path = PROMPTS_DIR / "real_interview" / f"{version}.md"
    return path.read_text()


def load_prep_plan_prompt(version: str = "v1") -> str:
    """Prep Plan question-suggestion prompt (user-pitched feature, see
    src/roundzero/prep_plan/suggest.py) - no round_type axis in the filename
    since the prompt itself is round-type-agnostic (round type is passed as
    context in the user message, same as load_real_interview_prompt's
    "hints" argument), same "lives directly under its own top-level prompts/
    folder" shape as load_committee_prompt/load_real_interview_prompt."""
    path = PROMPTS_DIR / "prep_plan" / f"{version}.md"
    return path.read_text()
