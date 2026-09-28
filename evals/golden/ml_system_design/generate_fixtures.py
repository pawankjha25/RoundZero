"""
Generates the golden fixtures under fixtures/*.json - run this to regenerate
them after a deliberate rubric/scoring change (re-review the printed
readiness_pct/hire_signal per scenario against each scenario's own
description before committing the regenerated fixtures - that review is the
whole point of a golden set, not something to skip because the script ran
clean).

RuleBasedEvaluator.evaluate() is a pure function of (transcript,
final_coverage) - no DB, no LLM, no network - so this only needs
roundzero.evaluation on the path; run with:
    python3 evals/golden/ml_system_design/generate_fixtures.py
from the repo root (needs the repo's venv active, same as pytest).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from roundzero.evaluation.evaluator import RuleBasedEvaluator

DIMS = ["framing", "architecture", "modeling", "data_training", "serving_scalability",
        "reliability", "evaluation_monitoring", "cost_efficiency", "trade_offs", "communication"]

PROBE_BANK = {
    "framing": "Let's clarify scale first - how many requests per second, and what's the latency budget?",
    "architecture": "Walk me through the high-level components and how they connect.",
    "modeling": "What model architecture are you choosing here, and why not a simpler one?",
    "data_training": "How would you get labeled training data for this, and how often do you retrain?",
    "serving_scalability": "Traffic spikes 10x during peak - how does your serving layer handle that?",
    "reliability": "One region goes down. What happens to in-flight requests?",
    "evaluation_monitoring": "How would you know in production if this model's quality degraded?",
    "cost_efficiency": "This design uses a lot of GPU capacity - how would you bring the cost down?",
    "trade_offs": "You chose consistency over availability here - walk me through that trade-off.",
    "communication": "Can you summarize your design so far in a couple of sentences?",
}

# One representative candidate answer per dimension. RuleBasedEvaluator's score
# is driven entirely by final_coverage + competency_tags/evidence count, never
# by the text content itself - so this wording doesn't change what's under
# test, it just keeps the fixtures readable as plausible interview transcripts
# rather than bracketed placeholders.
ANSWER_BANK = {
    "framing": "We're looking at roughly 50k requests per second at peak, sub-100ms p99, with hard isolation between tenants.",
    "architecture": "A gateway routes to per-tenant model servers behind an autoscaling pool, with a shared feature cache in front.",
    "modeling": "I'd start with a distilled model for the low-latency path and reserve the larger model for tenants that can tolerate more latency.",
    "data_training": "Labels come from a delayed-feedback pipeline, and we'd retrain weekly with a shadow-eval gate before promotion.",
    "serving_scalability": "Autoscaling on queue depth rather than CPU, with a pre-warmed buffer pool so a 10x spike doesn't cold-start GPUs.",
    "reliability": "Active-active across two regions with idempotent retries; in-flight requests fail over via a shared request log.",
    "evaluation_monitoring": "We'd track prediction drift against a held-out reference distribution and alert when it crosses a threshold, not just watch offline accuracy.",
    "cost_efficiency": "Batching small-tenant traffic onto shared GPU pools and falling back to CPU for tenants under a size threshold.",
    "trade_offs": "I chose availability over strict consistency here since a slightly stale ranking is better than a failed request for this use case.",
    "communication": "So to summarize: a multi-tenant gateway with per-tenant isolation, autoscaled serving, and drift-based monitoring feeding weekly retraining.",
}


def build_transcript(coverage_and_evidence: dict) -> list[dict]:
    transcript = []
    for dim, (status, evidence_count) in coverage_and_evidence.items():
        for _ in range(evidence_count):
            transcript.append({
                "speaker": "interviewer",
                "text": PROBE_BANK[dim],
                "phase": "high_level_design",
                "competency_tags": [dim],
            })
            transcript.append({
                "speaker": "candidate",
                "text": ANSWER_BANK[dim],
                "phase": "high_level_design",
                "competency_tags": [],
            })
    return transcript


SCENARIOS = {
    "ceiling_all_dimensions_exceed": {
        "description": "Every dimension COVERED with 3+ probes each - the ceiling case. All dimensions should hit the 4/4 bump and land STRONG HIRE.",
        "coverage": {d: ("COVERED", 3) for d in DIMS},
    },
    "floor_nothing_covered": {
        "description": "Every dimension NOT_COVERED, no evidence anywhere - the floor case. Every dimension scores 1/4, NO HIRE.",
        "coverage": {d: ("NOT_COVERED", 0) for d in DIMS},
    },
    "solid_target_level_meets_bar": {
        "description": "Every dimension COVERED but with only 1 probe each (not enough for the 4/4 bump) - independently handles target-level reasoning without exceeding it. Should land HIRE.",
        "coverage": {d: ("COVERED", 1) for d in DIMS},
    },
    "uniformly_weak_understanding": {
        "description": "Every dimension WEAK - candidate understood the areas but missed important considerations everywhere. Should land NO HIRE (33% readiness, below the 35% LEAN NO HIRE floor).",
        "coverage": {d: ("WEAK", 1) for d in DIMS},
    },
    "strong_architecture_weak_reliability": {
        "description": "Realistic mixed profile: strong on the heavily-weighted architecture/modeling/serving dimensions, weak on reliability and cost - a common staff-level gap pattern.",
        "coverage": {
            "framing": ("COVERED", 1), "architecture": ("COVERED", 3), "modeling": ("COVERED", 3),
            "data_training": ("COVERED", 1), "serving_scalability": ("COVERED", 3),
            "reliability": ("WEAK", 1), "evaluation_monitoring": ("WEAK", 1),
            "cost_efficiency": ("NOT_COVERED", 0), "trade_offs": ("COVERED", 1), "communication": ("COVERED", 1),
        },
    },
    "borderline_lean_hire": {
        "description": "Just enough to be a LEAN HIRE, not a clean HIRE - mostly WEAK with a few COVERED on the highest-weighted dimensions.",
        "coverage": {
            "framing": ("WEAK", 1), "architecture": ("COVERED", 1), "modeling": ("COVERED", 1),
            "data_training": ("WEAK", 1), "serving_scalability": ("COVERED", 1),
            "reliability": ("WEAK", 1), "evaluation_monitoring": ("WEAK", 1),
            "cost_efficiency": ("WEAK", 1), "trade_offs": ("WEAK", 1), "communication": ("COVERED", 1),
        },
    },
    "borderline_lean_no_hire": {
        "description": "WEAK everywhere except architecture and modeling (COVERED, one probe each) - understood the two most heavily-weighted areas but fell short broadly. Lands LEAN NO HIRE (43%), not NO HIRE - the distinction the rubric cares about between a total miss and a below-bar-but-partial showing.",
        "coverage": {
            "framing": ("WEAK", 1), "architecture": ("COVERED", 1), "modeling": ("COVERED", 1),
            "data_training": ("WEAK", 1), "serving_scalability": ("WEAK", 1),
            "reliability": ("WEAK", 1), "evaluation_monitoring": ("WEAK", 1),
            "cost_efficiency": ("WEAK", 1), "trade_offs": ("WEAK", 1), "communication": ("WEAK", 1),
        },
    },
    "strong_hire_near_ceiling": {
        "description": "Nearly every heavily-weighted dimension exceeds target (4/4), lightly-weighted ones only meet it - still comfortably STRONG HIRE.",
        "coverage": {
            "framing": ("COVERED", 3), "architecture": ("COVERED", 3), "modeling": ("COVERED", 3),
            "data_training": ("COVERED", 3), "serving_scalability": ("COVERED", 3),
            "reliability": ("COVERED", 3), "evaluation_monitoring": ("COVERED", 1),
            "cost_efficiency": ("COVERED", 1), "trade_offs": ("COVERED", 1), "communication": ("COVERED", 1),
        },
    },
    "narrow_scope_early_cutoff": {
        "description": "Candidate only got through requirements/architecture before time ran out - a realistic partial-round shape (as opposed to a deliberately-weak answer everywhere). Framing/architecture/communication COVERED, everything downstream genuinely NOT_COVERED because it was never reached.",
        "coverage": {
            "framing": ("COVERED", 1), "architecture": ("COVERED", 1), "modeling": ("WEAK", 1),
            "data_training": ("NOT_COVERED", 0), "serving_scalability": ("NOT_COVERED", 0),
            "reliability": ("NOT_COVERED", 0), "evaluation_monitoring": ("NOT_COVERED", 0),
            "cost_efficiency": ("NOT_COVERED", 0), "trade_offs": ("NOT_COVERED", 0), "communication": ("COVERED", 1),
        },
    },
    "deep_on_reliability_and_trade_offs": {
        "description": "A different strength profile than strong_architecture_weak_reliability - excels specifically at reliability and trade-off reasoning (the qualities the communication dimension's own note calls out as distinctly staff/principal signal), average elsewhere.",
        "coverage": {
            "framing": ("COVERED", 1), "architecture": ("WEAK", 1), "modeling": ("COVERED", 1),
            "data_training": ("COVERED", 1), "serving_scalability": ("WEAK", 1),
            "reliability": ("COVERED", 3), "evaluation_monitoring": ("COVERED", 1),
            "cost_efficiency": ("COVERED", 1), "trade_offs": ("COVERED", 3), "communication": ("COVERED", 1),
        },
    },
}

evaluator = RuleBasedEvaluator()
out_dir = os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(out_dir, exist_ok=True)

for scenario_id, spec in SCENARIOS.items():
    coverage = spec["coverage"]
    transcript = build_transcript(coverage)
    final_coverage = {d: status for d, (status, _ev) in coverage.items()}

    scored = evaluator.evaluate(
        round_id=f"golden-{scenario_id}",
        round_type="ml_system_design",
        transcript=transcript,
        final_coverage=final_coverage,
    )

    fixture = {
        "id": scenario_id,
        "source": "synthetic",
        "description": spec["description"],
        "transcript": transcript,
        "final_coverage": final_coverage,
        "expected": {
            "dimension_scores": {d.dimension: d.score for d in scored.dimension_scores},
            "readiness_pct": scored.readiness_pct,
            "hire_signal": scored.hire_signal,
        },
    }
    path = os.path.join(out_dir, f"{scenario_id}.json")
    with open(path, "w") as f:
        json.dump(fixture, f, indent=2)
        f.write("\n")
    print(f"{scenario_id:35s} readiness={scored.readiness_pct:3d}%  hire_signal={scored.hire_signal}")

print(f"\n{len(SCENARIOS)} synthetic fixtures written to {out_dir}")
