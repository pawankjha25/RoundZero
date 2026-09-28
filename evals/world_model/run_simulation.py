"""
Gate 2, offline: does the adaptive follow-up picker find the candidate's level
in fewer questions than a fixed or random order? (specs/005)

    python -m evals.world_model.run_simulation [--budget 25] [--runs 60] [--seed 0]

Evidence-level simulator (roundzero.worldmodel.simulator): each question yields
one evidence item sampled from the world model's own likelihood column at the
persona's true level, so this measures the POLICY. Pass criterion: adaptive
reaches the fixed order's final mean accuracy with <= 75% of the budget.
"""
from __future__ import annotations

import argparse

from roundzero.worldmodel import config, simulator

ROUND_TYPES = ["ml_system_design", "ml_depth", "technical_leadership", "xfn", "backend_system_design"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=25)
    parser.add_argument("--runs", type=int, default=60, help="runs per persona")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    all_pass = True
    for rt in ROUND_TYPES:
        comps = config.round_competencies(rt)
        if len(comps) < 2:
            print(f"{rt}: {len(comps)} competency - adaptive ordering does not apply, skipped")
            continue
        s = simulator.compare_policies(comps, runs_per_persona=args.runs, budget=args.budget, seed=args.seed)
        target = s["fixed"]["accuracy_by_q"][-1]
        q_adaptive = simulator.questions_to_accuracy(s["adaptive"]["accuracy_by_q"], target)
        ok = q_adaptive is not None and q_adaptive <= 0.75 * args.budget
        all_pass &= ok
        print(f"\n{rt} ({len(comps)} competencies, {s['fixed']['episodes']} episodes per policy)")
        for policy, v in s.items():
            curve = v["accuracy_by_q"]
            marks = ", ".join(f"q{i}={curve[i - 1]:.2f}" for i in (5, 10, 15, 20, 25) if i <= len(curve))
            print(f"  {policy:8s} accuracy {marks}")
        saving = 1 - (q_adaptive or args.budget + 1) / args.budget
        print(f"  adaptive needs {q_adaptive} of {args.budget} questions to match fixed "
              f"({saving:.0%} fewer) -> {'PASS' if ok else 'FAIL'} (target: 25% fewer)")
    print(f"\nGate 2 (simulator): {'PASS' if all_pass else 'FAIL'} - keep ROUNDZERO_WM_ADAPTIVE=shadow until it passes "
          "here AND on real rounds.")


if __name__ == "__main__":
    main()
