"""
Terminal test harness for the ML System Design interviewer - Milestone 1, step 1.
No database, no API, no auth: the cheapest possible way to judge whether the
adaptive probing is actually good before building anything else around it.

Usage (from repo root, with .venv active and ANTHROPIC_API_KEY set):
    python -m roundzero.interviewers.ml_system_design.cli --level principal --minutes 45
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv

from roundzero.domain.enums import InterviewerAction
from roundzero.domain.interview import ConversationState, TargetRole
from roundzero.interviewers.ml_system_design.agent import MLSystemDesignInterviewer
from roundzero.llm.providers.anthropic_provider import AnthropicGateway
from roundzero.llm.providers.mock_provider import MockLLMGateway


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Talk to the ML System Design interviewer in your terminal.")
    parser.add_argument("--role", default="ml_engineer")
    parser.add_argument("--level", default="principal")
    parser.add_argument("--domain", default="ml_infra")
    parser.add_argument("--minutes", type=int, default=45)
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use a scripted mock gateway instead of a real API call - no ANTHROPIC_API_KEY "
        "needed. Proves the CLI/state-machine plumbing works; does NOT test real interview "
        "quality, which needs the real gateway.",
    )
    args = parser.parse_args()

    target_role = TargetRole(role_family=args.role, level=args.level, domain=args.domain)
    if args.mock:
        print("*** MOCK MODE - scripted responses, not a real model. Use for testing the CLI/state machine only. ***")
        llm = MockLLMGateway()
    else:
        llm = AnthropicGateway()
    interviewer = MLSystemDesignInterviewer(llm)
    scenario = interviewer.pick_scenario(target_role)
    state = ConversationState(time_remaining_sec=args.minutes * 60)

    print("\n=== Round Zero - ML System Design (CLI test harness) ===")
    print(f"Target: {args.role} / {args.level} / {args.domain}")
    print(f"Scenario: {scenario['prompt']}\n")

    candidate_message: str | None = None
    while True:
        output = interviewer.next_turn(scenario=scenario, state=state, candidate_message=candidate_message)
        print(f"\n[{output.phase.value}] Interviewer: {output.utterance}\n")

        if output.action == InterviewerAction.WRAP or state.time_remaining_sec <= 0:
            print("--- Interview ended (SUBMITTED - not evaluated yet, that's milestone 2) ---")
            break

        candidate_message = input("You: ")
        # Crude wall-clock stand-in for CLI testing - the real orchestrator tracks
        # actual elapsed time server-side (milestone-1.md build checklist).
        state.time_remaining_sec -= 90


if __name__ == "__main__":
    main()
