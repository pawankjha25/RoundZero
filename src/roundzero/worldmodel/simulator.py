"""
Simulated candidates (specs/005) - two levels of fidelity:

1. Evidence-level (this module's main use, no LLM, deterministic by seed): a
   persona has a hidden true level per competency, and each probe on a
   competency yields one evidence item sampled from the world model's own
   likelihood column at that true level. This is the cheap Gate 2 testbed:
   does the adaptive picker reach a confident, correct level in fewer
   questions than a fixed order or random order? Because the simulator samples
   from the same table the belief uses, it measures the POLICY, not the table -
   the table's own accuracy is Gate 3's job (learn.py).

2. Text-level (SimulatedCandidate): an LLM role-plays a persona with the same
   hidden levels (prompts/world_model/sim_candidate/v1.md), for regression runs
   through the real interviewer + extractor. Results from simulated runs are
   always reported separately from real candidates.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass

from roundzero.llm.gateway import LLMGateway
from roundzero.worldmodel import belief as bl
from roundzero.worldmodel import config, picker
from roundzero.worldmodel.models import Evidence

POLICIES = ("adaptive", "fixed", "random")


@dataclass(frozen=True)
class Persona:
    name: str
    true_levels: dict[str, int]  # competency -> level index (0 = below_senior ... 3 = principal)


def default_personas(comps: list[str]) -> list[Persona]:
    def uniform(level: int) -> dict[str, int]:
        return {c: level for c in comps}

    def mixed(base: int, overrides: dict[int, int]) -> dict[str, int]:
        levels = uniform(base)
        for i, lvl in overrides.items():
            if i < len(comps):
                levels[comps[i]] = lvl
        return levels

    return [
        Persona("uniform_below_senior", uniform(0)),
        Persona("uniform_senior", uniform(1)),
        Persona("uniform_staff", uniform(2)),
        Persona("uniform_principal", uniform(3)),
        Persona("staff_with_one_senior_gap", mixed(2, {len(comps) - 1: 1})),
        Persona("senior_with_one_staff_strength", mixed(1, {0: 2})),
        Persona("spiky_principal_and_senior", mixed(2, {0: 3, 1: 1})),
        Persona("borderline_staff", mixed(1, {0: 2, 2: 2})),
    ]


def sample_evidence(comp: str, true_level: int, rng: random.Random, turn_index: int, strength: float = 0.8) -> Evidence:
    weights = [config.likelihood_row(comp, pol)[true_level] for pol in config.POLARITIES]
    polarity = rng.choices(list(config.POLARITIES), weights=weights, k=1)[0]
    return Evidence(
        turn_index=turn_index,
        dimension=f"sim_{comp}",
        competency=comp,
        criterion=f"simulated probe on {comp}",
        polarity=polarity,
        span=None,
        strength=strength,
        extractor_version="simulator-v1",
    )


def run_episode(
    persona: Persona,
    comps: list[str],
    policy: str,
    rng: random.Random,
    *,
    target_level: str = "staff",
    budget: int = 12,
    threshold: float = 0.8,
) -> dict:
    belief = bl.initial_belief(target_level, comps)
    choices: list[str] = []
    questions_to_all_confident: int | None = None
    accuracy_by_q: list[float] = []
    for q in range(budget):
        if policy == "adaptive":
            decision = picker.choose(belief, after_turn_index=q, recent_choices=choices,
                                     time_remaining_sec=10_000, mode="shadow")
            comp = decision.chosen.competency if decision.chosen else comps[q % len(comps)]
        elif policy == "fixed":
            comp = comps[q % len(comps)]
        elif policy == "random":
            comp = rng.choice(comps)
        else:
            raise ValueError(policy)
        choices.append(comp)
        ev = sample_evidence(comp, persona.true_levels[comp], rng, turn_index=q)
        belief = bl.apply_evidence(belief, [ev])
        correct = sum(1 for c in comps if belief.mode(c) == persona.true_levels[c]) / len(comps)
        accuracy_by_q.append(correct)
        if questions_to_all_confident is None and all(belief.confidence(c) >= threshold for c in comps):
            questions_to_all_confident = q + 1
    return {
        "persona": persona.name,
        "policy": policy,
        "choices": choices,
        "accuracy_by_q": accuracy_by_q,
        "final_accuracy": accuracy_by_q[-1] if accuracy_by_q else 0.0,
        "questions_to_all_confident": questions_to_all_confident,
    }


def compare_policies(
    comps: list[str],
    *,
    runs_per_persona: int = 50,
    budget: int = 12,
    seed: int = 0,
    target_level: str = "staff",
) -> dict:
    """Mean accuracy per question count and questions-to-confidence per policy.
    Every policy sees the same seeds per persona (paired comparison)."""
    personas = default_personas(comps)
    summary: dict[str, dict] = {}
    for policy in POLICIES:
        acc = [0.0] * budget
        q_conf: list[int] = []
        n = 0
        for p_i, persona in enumerate(personas):
            for r in range(runs_per_persona):
                rng = random.Random(seed * 1_000_003 + p_i * 10_007 + r)
                res = run_episode(persona, comps, policy, rng, target_level=target_level, budget=budget)
                for i, a in enumerate(res["accuracy_by_q"]):
                    acc[i] += a
                q_conf.append(res["questions_to_all_confident"] or budget + 1)
                n += 1
        summary[policy] = {
            "episodes": n,
            "accuracy_by_q": [round(a / n, 4) for a in acc],
            "mean_questions_to_all_confident": round(sum(q_conf) / len(q_conf), 3),
            "share_reaching_confidence": round(sum(1 for q in q_conf if q <= budget) / len(q_conf), 3),
        }
    return summary


def questions_to_accuracy(accuracy_by_q: list[float], target: float) -> int | None:
    for i, a in enumerate(accuracy_by_q):
        if a >= target:
            return i + 1
    return None


class SimulatedCandidate:
    """Text-level persona for end-to-end regression runs."""

    def __init__(self, llm: LLMGateway, persona: Persona, description: str, prompt_version: str = "v1"):
        self._llm = llm
        self._persona = persona
        levels = "\n".join(
            f"- {config.competency(c)['label']}: {config.level_label(lvl)}"
            for c, lvl in persona.true_levels.items()
        )
        self._system = config.load_wm_prompt("sim_candidate", prompt_version).format(
            persona=description, levels=levels
        )

    def answer(self, transcript: list[dict]) -> str:
        history = "\n".join(f"{t['speaker']}: {t['text']}" for t in transcript)
        raw = self._llm.complete_json(system=self._system, user_message=f"Transcript so far:\n{history}")
        return str(json.loads(raw).get("answer", "")).strip()
