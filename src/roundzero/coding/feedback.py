"""
LLM-generated, interviewer-style code quality feedback for the Coding
workspace's Run button - separate from CodeExecutionProvider on purpose (see
execution.py's module docstring): running code is a mechanical concern
(did the tests pass), quality feedback is a judgment call a real interviewer
makes regardless of whether every test happened to pass. Reuses whichever LLM
gateway apps/api/orchestrator.get_gateway() already selects for the
interviewer (Gemini/Anthropic/mock) - no new provider selection needed here.

Best-effort by design: apps/api/routes/rounds.py calls this after execution
and swallows any failure, so a flaky/unavailable LLM never breaks the Run
button itself - the mechanical test results are still returned either way.
"""
from __future__ import annotations

import json

from roundzero.coding.execution import CodeQualityFeedback, TestCaseResult
from roundzero.llm.gateway import LLMGateway

_SYSTEM_PROMPT = """You are a senior software engineer giving feedback on a candidate's
solution during a live technical coding interview, the way a real onsite interviewer
would - direct, specific, and honest rather than encouraging for its own sake.

You will be given the candidate's code, whether it was actually executed, and the
result of any test cases that ran. Judge the code itself (readability, structure,
naming, edge-case handling, time/space complexity) - do not just restate the test
results. If the code was not executed, say so plainly and give feedback based on
reading the code, without claiming to have verified it runs.

Respond with a single JSON object matching exactly this shape:
{
  "summary": "1-2 sentence overall read on this submission",
  "strengths": ["short bullet", "..."],
  "concerns": ["short bullet", "..."],
  "complexity_note": "time/space complexity, one sentence, or null if not applicable",
  "interviewer_followup": "one question a real interviewer would ask next, or null"
}
Return only the JSON object, no other text."""


def _build_user_message(
    *, language: str, code: str, executed: bool, test_results: list[TestCaseResult]
) -> str:
    if test_results:
        results_lines = "\n".join(
            f"- {r.name}: {'PASSED' if r.passed else 'FAILED' if r.passed is False else 'NOT RUN'}"
            + (f" (output/error: {r.actual_output})" if r.actual_output else "")
            for r in test_results
        )
    else:
        results_lines = "(no test cases)"

    return (
        f"Language: {language}\n"
        f"Code was executed: {executed}\n\n"
        f"Candidate's code:\n```{language}\n{code}\n```\n\n"
        f"Test results:\n{results_lines}\n\n"
        f"Give your feedback as the single JSON object described in your instructions."
    )


def generate_code_feedback(
    llm: LLMGateway,
    *,
    language: str,
    code: str,
    executed: bool,
    test_results: list[TestCaseResult],
) -> CodeQualityFeedback:
    user_message = _build_user_message(
        language=language, code=code, executed=executed, test_results=test_results
    )
    raw = llm.complete_json(system=_SYSTEM_PROMPT, user_message=user_message, max_tokens=768)
    return CodeQualityFeedback.model_validate(json.loads(raw))
