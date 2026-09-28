"""
PythonSubprocessExecutionProvider (2026-09) - real Python code execution for
the Coding workspace's Run button, and roundzero.coding.feedback's LLM code
quality review. No network: the feedback tests use a fake LLMGateway, same
pattern as test_ml_system_design_agent_smoke.py.
"""
from __future__ import annotations

import json

from roundzero.coding.execution import (
    CodeQualityFeedback,
    CodeTestCase,
    PythonSubprocessExecutionProvider,
)
from roundzero.coding.feedback import generate_code_feedback
from roundzero.llm.gateway import LLMGateway

TWO_SUM_CORRECT = "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n"
TWO_SUM_WRONG = "def two_sum(nums, target):\n    return [0, 0]\n"
TWO_SUM_RAISES = "def two_sum(nums, target):\n    raise ValueError('nope')\n"

TEST_CASES = [
    CodeTestCase(name="example_1", input=json.dumps([[2, 7, 11, 15], 9]), expected_output=json.dumps([0, 1])),
    CodeTestCase(name="example_2", input=json.dumps([[3, 2, 4], 6]), expected_output=json.dumps([1, 2])),
]


def test_correct_python_solution_passes_real_tests():
    provider = PythonSubprocessExecutionProvider()
    result = provider.run(language="python", code=TWO_SUM_CORRECT, test_cases=TEST_CASES, entry_point="two_sum")

    assert result.executed is True
    assert len(result.test_results) == 2
    assert all(tc.passed is True for tc in result.test_results)


def test_incorrect_python_solution_fails_real_tests_without_crashing():
    provider = PythonSubprocessExecutionProvider()
    result = provider.run(language="python", code=TWO_SUM_WRONG, test_cases=TEST_CASES, entry_point="two_sum")

    assert result.executed is True
    assert all(tc.passed is False for tc in result.test_results)


def test_raising_candidate_code_reports_the_error_not_a_fabricated_pass():
    provider = PythonSubprocessExecutionProvider()
    result = provider.run(language="python", code=TWO_SUM_RAISES, test_cases=TEST_CASES, entry_point="two_sum")

    assert result.executed is True
    assert all(tc.passed is False for tc in result.test_results)
    assert all(tc.actual_output and "ValueError" in tc.actual_output for tc in result.test_results)


def test_non_python_language_still_gets_the_honest_mock_response():
    provider = PythonSubprocessExecutionProvider()
    result = provider.run(language="java", code="class X {}", test_cases=TEST_CASES, entry_point="two_sum")

    assert result.executed is False
    assert all(tc.passed is None for tc in result.test_results)


def test_missing_entry_point_never_silently_no_ops_as_a_pass():
    provider = PythonSubprocessExecutionProvider()
    result = provider.run(language="python", code=TWO_SUM_CORRECT, test_cases=TEST_CASES, entry_point=None)

    assert result.executed is False
    assert all(tc.passed is None for tc in result.test_results)


def test_infinite_loop_is_killed_by_the_timeout():
    # The infinite loop can be killed by subprocess.run's own wall-clock
    # timeout, or by the CPU rlimit firing first (whichever wins the race) -
    # either way it must return promptly with an honest all-failed result,
    # never hang the request or fabricate a pass.
    import time

    provider = PythonSubprocessExecutionProvider()
    started = time.monotonic()
    result = provider.run(
        language="python",
        code="def two_sum(nums, target):\n    while True:\n        pass\n",
        test_cases=TEST_CASES,
        entry_point="two_sum",
    )
    elapsed = time.monotonic() - started

    assert elapsed < 10, "execution should be killed well before it could hang"
    assert result.executed is True
    assert all(tc.passed is False for tc in result.test_results)


class FakeFeedbackGateway(LLMGateway):
    def __init__(self, payload: dict):
        self._payload = payload

    def complete_json(self, *, system: str, user_message: str, max_tokens: int = 1024) -> str:
        assert "Candidate's code" in user_message
        return json.dumps(self._payload)


def test_generate_code_feedback_parses_the_llm_response():
    gateway = FakeFeedbackGateway(
        {
            "summary": "Correct and efficient hash-map solution.",
            "strengths": ["Single pass, O(n) time"],
            "concerns": ["No handling for empty input"],
            "complexity_note": "O(n) time, O(n) space",
            "interviewer_followup": "What if the array is empty?",
        }
    )

    feedback = generate_code_feedback(
        gateway,
        language="python",
        code=TWO_SUM_CORRECT,
        executed=True,
        test_results=[],
    )

    assert isinstance(feedback, CodeQualityFeedback)
    assert "hash-map" in feedback.summary
    assert feedback.interviewer_followup == "What if the array is empty?"


# --- Sandboxing hardening (2026-09-01) ------------------------------------
#
# Before this pass, PythonSubprocessExecutionProvider ran candidate code with
# this process's real environment (a live path to reading GEMINI_API_KEY/
# OPENAI_API_KEY/etc. via os.environ) and no restriction at all on
# filesystem, network, or process access. These tests prove the concrete
# exploits are blocked now - not a claim of full sandboxing (see the class
# docstring's honest gap), just the specific things that were live risks.

import os as _os  # noqa: E402

from roundzero.coding.execution import _static_safety_check  # noqa: E402


def _run_blocked(code: str) -> None:
    provider = PythonSubprocessExecutionProvider()
    result = provider.run(language="python", code=code, test_cases=TEST_CASES, entry_point="two_sum")
    assert result.executed is False, f"expected this to be blocked before running: {code!r}"
    assert all(tc.passed is None for tc in result.test_results), "a blocked run must never fabricate a pass/fail"
    assert result.stderr, "a blocked run must explain why"


def test_import_os_is_blocked_before_it_ever_runs():
    _run_blocked("import os\ndef two_sum(nums, target):\n    return list(os.environ.items())\n")


def test_import_subprocess_is_blocked():
    _run_blocked("import subprocess\ndef two_sum(nums, target):\n    return subprocess.run(['ls']).returncode\n")


def test_import_socket_is_blocked():
    _run_blocked("import socket\ndef two_sum(nums, target):\n    return 0\n")


def test_open_call_is_blocked():
    _run_blocked("def two_sum(nums, target):\n    return open('/etc/passwd').read()\n")


def test_eval_call_is_blocked():
    _run_blocked("def two_sum(nums, target):\n    return eval('1+1')\n")


def test_dunder_import_call_is_blocked():
    _run_blocked("def two_sum(nums, target):\n    return __import__('os').getpid()\n")


def test_ordinary_solution_is_never_flagged_by_the_denylist():
    assert _static_safety_check(TWO_SUM_CORRECT) is None
    # Common, legitimate stdlib usage for interview-style solutions must stay
    # allowed - the denylist targets escape hatches, not general Python.
    benign = (
        "import math\nimport collections\nimport itertools\nimport json as j\n"
        "from typing import List\n"
        "def two_sum(nums, target):\n"
        "    counts = collections.Counter(nums)\n"
        "    return math.floor(sum(nums) / max(1, len(nums)))\n"
    )
    assert _static_safety_check(benign) is None


def test_candidate_code_cannot_read_this_process_real_env_vars():
    # Regression for the concrete secret-exfiltration path this pass closed:
    # even if the AST denylist had a bypass (defense in depth, not the only
    # layer), the child process must not inherit this process's real
    # environment. Bypasses _static_safety_check for this one test (via
    # monkeypatch) so candidate code can actually `import os` and try to read
    # a canary secret - proving the env-stripping layer holds on its own,
    # independent of the denylist.
    from unittest.mock import patch

    canary_name = "ROUNDZERO_TEST_CANARY_SECRET"
    _os.environ[canary_name] = "should-never-be-visible-to-candidate-code"
    code = (
        f"import os\n"
        f"def two_sum(nums, target):\n"
        f"    return [1 if os.environ.get({canary_name!r}) else 0, len(os.environ)]\n"
    )
    try:
        with patch("roundzero.coding.execution._static_safety_check", return_value=None):
            provider = PythonSubprocessExecutionProvider()
            result = provider.run(language="python", code=code, test_cases=TEST_CASES, entry_point="two_sum")
        assert result.executed is True
        for tc in result.test_results:
            # actual_output is a JSON-encoded [flag, env_var_count]; flag must
            # be 0 (canary not found) and env_var_count must be tiny (PATH
            # only), not the dozens of real vars this test process has.
            assert tc.actual_output is not None
            flag, env_count = json.loads(tc.actual_output)
            assert flag == 0, "candidate code could read this process's real secret via os.environ"
            assert env_count <= 2, f"subprocess got {env_count} env vars, expected ~1 (PATH only)"
    finally:
        del _os.environ[canary_name]
