"""
tasks.md item 4: scenarios.yaml grew from 1 to 10 seeds, and
MLSystemDesignInterviewer.pick_scenario() grew from "always return the first
level match" to real level+domain filtering, random selection, and
recent-attempt exclusion (see pick_scenario's docstring and
orchestrator.create_round's recent_scenario_ids query). This locks that
behavior in with no network/LLM calls - a fake gateway is enough since only
scenario selection is under test, not turn generation.
"""
from __future__ import annotations

from roundzero.domain.interview import TargetRole
from roundzero.interviewers.ml_system_design.agent import MLSystemDesignInterviewer
from roundzero.llm.gateway import LLMGateway


class UnusedGateway(LLMGateway):
    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        raise AssertionError("pick_scenario() should never call the LLM gateway")


def _interviewer() -> MLSystemDesignInterviewer:
    return MLSystemDesignInterviewer(UnusedGateway())


def test_at_least_ten_scenarios_seeded():
    # Definition of Done (.claude/skills/add-interview-round): 10+ seeds.
    assert len(_interviewer()._scenarios) >= 10


def test_pick_scenario_only_returns_level_and_domain_matches_when_available():
    interviewer = _interviewer()
    role = TargetRole(role_family="ml_engineer", level="senior", domain="ml_infra")
    for _ in range(50):
        scenario = interviewer.pick_scenario(role)
        assert "senior" in scenario["level"]
        assert not scenario.get("domain") or "ml_infra" in scenario["domain"]


def test_pick_scenario_honors_exclude_ids_when_alternatives_exist():
    interviewer = _interviewer()
    role = TargetRole(role_family="ml_engineer", level="principal", domain="general_ml")
    exclude = frozenset({"multi_tenant_inference_platform"})
    for _ in range(50):
        assert interviewer.pick_scenario(role, exclude_ids=exclude)["id"] != "multi_tenant_inference_platform"


def test_pick_scenario_falls_back_gracefully_when_exclude_ids_covers_everything():
    # Excluding every known id should never raise - it should fall back to
    # ignoring the exclusion rather than returning nothing.
    interviewer = _interviewer()
    role = TargetRole(role_family="ml_engineer", level="senior", domain="ml_infra")
    all_ids = frozenset(s.get("id", s.get("name", "")) for s in interviewer._scenarios)
    scenario = interviewer.pick_scenario(role, exclude_ids=all_ids)
    assert scenario is not None


def test_pick_scenario_never_raises_for_any_level_domain_combo():
    interviewer = _interviewer()
    for level in ("senior", "staff", "principal"):
        for domain in ("ml_infra", "general_ml"):
            role = TargetRole(role_family="ml_engineer", level=level, domain=domain)
            scenario = interviewer.pick_scenario(role)
            assert scenario is not None and scenario.get("prompt")
