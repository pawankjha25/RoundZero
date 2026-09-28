"""
Code execution abstraction for the Coding interview workspace.

Mirrors roundzero.llm.gateway.LLMGateway: an abstract provider interface plus
provider selection lives at get_execution_provider() (apps/api routes call
that, the same way apps/api/orchestrator.get_gateway() picks an LLM provider),
so a real container-sandboxed executor can be dropped in later behind this
same interface without touching callers.

Two implementations today:
- MockCodeExecutionProvider: never executes anything, never fabricates a
  pass/fail. TestCaseResult.passed is `None` (not True/False) for every case,
  and stdout says plainly that no sandbox is configured.
- PythonSubprocessExecutionProvider (2026-09, hardened 2026-09-01): actually
  runs Python candidate code as a real subprocess. Layered, best-effort
  mitigations, not a real sandbox - read the class docstring for the honest
  gap before reusing this anywhere a genuinely untrusted candidate (not just
  a mock interview candidate) could submit code: (1) an AST denylist that
  rejects code before it ever runs if it imports os/subprocess/socket/etc. or
  calls eval/exec/open/__import__ - see _static_safety_check; (2) the child
  process gets a minimal, explicit environment (PATH only), not this
  process's real one, which otherwise would have handed candidate code a
  direct read on GEMINI_API_KEY/OPENAI_API_KEY/DEEPGRAM_API_KEY/etc. via
  os.environ (this was a real, live exfiltration path before this pass, not
  a theoretical one - this repo's own .env sits right there in the working
  tree); (3) a wall-clock timeout and best-effort CPU/memory/process-count
  rlimits. None of this is container/VM isolation - a sufficiently
  determined author can likely still find an obfuscated bypass through
  allowed builtins, and the filesystem/network are only restricted by the
  denylist catching the obvious entry points, not by an OS-level jail. Safe
  enough to raise the bar past "accidental damage or a curious candidate
  poking at os.environ," not safe enough for a real multi-tenant, hostile-
  candidate deployment - that still needs real process isolation
  (Docker/gVisor/Firecracker or a hosted judge service) behind this same
  interface. Non-Python languages fall back to MockCodeExecutionProvider's
  honest "not executed" behavior until real per-language execution is built.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CodeTestCase(BaseModel):
    """`input` and `expected_output` are free-form strings for
    MockCodeExecutionProvider (display-only), but PythonSubprocessExecutionProvider
    requires them to be JSON: `input` a JSON array of positional arguments to
    call the candidate's entry-point function with, `expected_output` the JSON
    value the call should return. Leave `expected_output` empty for a test
    that only checks the call doesn't raise."""

    name: str
    input: str | None = None
    expected_output: str | None = None


class TestCaseResult(BaseModel):
    """`passed = None` means "not run" - distinct from True/False, so a mock or
    not-yet-configured provider can never be mistaken for a real verdict."""

    name: str
    passed: bool | None = None
    actual_output: str | None = None


class CodeQualityFeedback(BaseModel):
    """LLM-generated, interviewer-style read on the submitted code - separate
    from test_results (mechanical pass/fail) because a real interviewer
    evaluates readability, complexity and edge-case handling regardless of
    whether every test happened to pass. See roundzero.coding.feedback."""

    summary: str
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    complexity_note: str | None = None
    interviewer_followup: str | None = None


class CodeExecutionResult(BaseModel):
    stdout: str
    stderr: str = ""
    test_results: list[TestCaseResult] = Field(default_factory=list)
    executed: bool = False
    ran_at: datetime = Field(default_factory=_now)
    feedback: CodeQualityFeedback | None = None


class CodeExecutionProvider(ABC):
    """Provider interface for running candidate code. Implementations decide
    how (or whether) code actually executes; callers (apps/api routes) never
    execute code themselves."""

    @abstractmethod
    def run(
        self,
        *,
        language: str,
        code: str,
        test_cases: list[CodeTestCase],
        entry_point: str | None = None,
    ) -> CodeExecutionResult:
        raise NotImplementedError


class MockCodeExecutionProvider(CodeExecutionProvider):
    """Local-safe placeholder: never executes code, never fabricates a
    pass/fail. Returns an explicit "not executed" result so the frontend's
    Run button and test-case badges have a real, honest response to render
    while no sandbox is configured (or, now, for any language other than
    Python - see PythonSubprocessExecutionProvider)."""

    def run(
        self,
        *,
        language: str,
        code: str,
        test_cases: list[CodeTestCase],
        entry_point: str | None = None,
    ) -> CodeExecutionResult:
        return CodeExecutionResult(
            stdout=(
                f"Not executed - no secure code execution sandbox is configured yet "
                f"for {language}. This is a mock response; your code was saved but not run."
            ),
            stderr="",
            executed=False,
            test_results=[TestCaseResult(name=tc.name, passed=None, actual_output=None) for tc in test_cases],
        )


# AST denylist - checked before any candidate code ever runs (_static_safety_check).
# Not exhaustive and not a substitute for real process isolation (see the module
# and class docstrings' honest gap) - this stops the concrete, obvious escapes:
# reading this process's secrets via os.environ, reading/writing arbitrary files,
# opening network connections, or spawning more processes.
_BLOCKED_IMPORT_MODULES = {
    "os", "subprocess", "sys", "socket", "shutil", "ctypes", "multiprocessing",
    "threading", "importlib", "pty", "pathlib", "http", "urllib", "ftplib",
    "smtplib", "ssl", "signal", "resource", "asyncio",
}
_BLOCKED_CALL_NAMES = {"eval", "exec", "compile", "__import__", "open", "input", "breakpoint", "globals", "vars"}


def _static_safety_check(code: str) -> str | None:
    """Returns None when `code` passes the denylist, or a human-readable
    reason when it doesn't. A denylist over an AST, not a real sandbox - see
    the class docstring above for what this does and doesn't guarantee."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BLOCKED_IMPORT_MODULES:
                    return f"import of '{alias.name}' is not allowed in this sandbox"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _BLOCKED_IMPORT_MODULES:
                return f"import from '{node.module}' is not allowed in this sandbox"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _BLOCKED_CALL_NAMES:
                return f"calling '{node.func.id}(...)' is not allowed in this sandbox"
    return None


# The driver script executed in the subprocess. Kept as a template rather than
# an f-string so candidate code never gets string-interpolated into it -
# candidate code is written to its own file (solution.py) and imported
# normally; only the entry-point name and test-case list cross into this
# script, both JSON/repr-encoded so nothing here is ever eval'd from
# untrusted text.
_PYTHON_DRIVER_TEMPLATE = '''
import json, sys

RESULTS_SENTINEL = "##ROUNDZERO_RESULTS##"
test_cases = json.loads({test_cases_json!r})
entry_point = {entry_point!r}

try:
    import solution
except Exception as e:
    print(RESULTS_SENTINEL)
    print(json.dumps({{"import_error": f"{{type(e).__name__}}: {{e}}"}}))
    sys.exit(0)

fn = getattr(solution, entry_point, None)
results = []
if fn is None:
    for tc in test_cases:
        results.append({{"name": tc["name"], "passed": False, "actual": None,
                          "error": f"function '{{entry_point}}' not found in your code"}})
else:
    for tc in test_cases:
        name = tc["name"]
        try:
            args = json.loads(tc["input"]) if tc.get("input") else []
            actual = fn(*args)
            expected_raw = tc.get("expected_output")
            if expected_raw:
                expected = json.loads(expected_raw)
                passed = actual == expected
            else:
                passed = None
            results.append({{"name": name, "passed": passed, "actual": actual, "error": None}})
        except Exception as e:
            results.append({{"name": name, "passed": False, "actual": None,
                              "error": f"{{type(e).__name__}}: {{e}}"}})

print(RESULTS_SENTINEL)
print(json.dumps(results))
'''

_TIMEOUT_SEC = 5
_MEMORY_LIMIT_MB = 256
_RESULTS_SENTINEL = "##ROUNDZERO_RESULTS##"


def _apply_resource_limits() -> None:
    """Best-effort caps on the child process (POSIX only - not supported/
    enforced on every platform, e.g. RLIMIT_AS is unreliable on macOS, which
    is where this actually runs today). Each limit is applied independently
    and failures are swallowed on purpose: this is a courtesy layer on top of
    the AST denylist (_static_safety_check) and the stripped-down subprocess
    environment, not the whole safety story - see
    PythonSubprocessExecutionProvider's class docstring for the honest gap."""

    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (_TIMEOUT_SEC, _TIMEOUT_SEC))
    except Exception:
        pass
    try:
        import resource

        mem_bytes = _MEMORY_LIMIT_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    except Exception:
        pass
    try:
        import resource

        # Caps forking/spawning more processes - a fork bomb is otherwise not
        # stopped by a CPU or wall-clock timeout alone. The driver itself
        # spawns none, so a low limit doesn't affect legitimate solutions.
        resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
    except Exception:
        pass
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    except Exception:
        pass


class PythonSubprocessExecutionProvider(CodeExecutionProvider):
    """Runs Python candidate code for real, as a subprocess, against JSON-
    encoded test cases calling a named entry-point function. Falls back to
    MockCodeExecutionProvider's honest "not executed" behavior for any
    non-Python language, or when no entry_point is given (nothing to call).

    Layered, best-effort mitigations (2026-09-01), still NOT a real security
    sandbox:
      1. _static_safety_check rejects the code before it ever runs if it
         imports os/subprocess/socket/etc. or calls eval/exec/open/__import__.
      2. The child process gets a minimal, explicit environment (PATH only) -
         not this process's real one. Before this, candidate code could read
         GEMINI_API_KEY/OPENAI_API_KEY/DEEPGRAM_API_KEY/etc. straight out of
         os.environ; that was a real, live exfiltration path, not a
         theoretical one, since this app's own secrets live in this same
         process's environment.
      3. A wall-clock timeout plus best-effort CPU/memory/process-count/open-
         file rlimits (_apply_resource_limits).

    None of this is container/VM isolation. The denylist only catches the
    obvious entry points to the filesystem/network/process table - a
    sufficiently determined author can likely still find an obfuscated
    bypass through allowed builtins. This is enough to raise the bar past
    "accidental damage or a curious candidate poking at os.environ," not
    enough for a real multi-tenant, hostile-candidate deployment. Before this
    ever runs code from a genuinely untrusted candidate in production, it
    must be replaced (or gated) by real process isolation - a container
    (Docker/gVisor/Firecracker) or a hosted judge service - behind this same
    CodeExecutionProvider interface.
    """

    def __init__(self) -> None:
        self._mock = MockCodeExecutionProvider()

    def run(
        self,
        *,
        language: str,
        code: str,
        test_cases: list[CodeTestCase],
        entry_point: str | None = None,
    ) -> CodeExecutionResult:
        if language != "python":
            return self._mock.run(language=language, code=code, test_cases=test_cases, entry_point=entry_point)
        if not entry_point:
            return CodeExecutionResult(
                stdout="No entry-point function is configured for this problem, so nothing can be called - your code was saved but not run.",
                stderr="",
                executed=False,
                test_results=[TestCaseResult(name=tc.name, passed=None, actual_output=None) for tc in test_cases],
            )

        violation = _static_safety_check(code)
        if violation:
            return CodeExecutionResult(
                stdout="",
                stderr=(
                    f"Blocked before running: {violation}. Interview solutions here shouldn't "
                    "need file, network, or process access - if this looks like a false "
                    "positive, mention it to your interviewer."
                ),
                executed=False,
                test_results=[TestCaseResult(name=tc.name, passed=None, actual_output=None) for tc in test_cases],
            )

        with tempfile.TemporaryDirectory(prefix="rz_exec_") as tmpdir:
            with open(os.path.join(tmpdir, "solution.py"), "w") as f:
                f.write(code)

            driver_source = _PYTHON_DRIVER_TEMPLATE.format(
                test_cases_json=json.dumps([tc.model_dump() for tc in test_cases]),
                entry_point=entry_point,
            )
            with open(os.path.join(tmpdir, "driver.py"), "w") as f:
                f.write(driver_source)

            try:
                proc = subprocess.run(
                    [sys.executable, "driver.py"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=_TIMEOUT_SEC,
                    preexec_fn=_apply_resource_limits if os.name == "posix" else None,
                    # Minimal, explicit environment - NOT this process's real
                    # os.environ (see class docstring: that's a live secret-
                    # exfiltration path, not a hypothetical one). PATH is
                    # enough for the interpreter itself to run; nothing here
                    # should need more.
                    env={"PATH": os.environ.get("PATH", "")},
                )
            except subprocess.TimeoutExpired:
                return CodeExecutionResult(
                    stdout="",
                    stderr=f"Execution timed out after {_TIMEOUT_SEC}s.",
                    executed=True,
                    test_results=[TestCaseResult(name=tc.name, passed=False, actual_output=None) for tc in test_cases],
                )

        return self._parse_result(proc.stdout or "", proc.stderr or "", test_cases)

    def _parse_result(
        self, stdout: str, stderr: str, test_cases: list[CodeTestCase]
    ) -> CodeExecutionResult:
        if _RESULTS_SENTINEL not in stdout:
            # Driver crashed before it could emit results - surface whatever
            # came out rather than pretending nothing happened.
            return CodeExecutionResult(
                stdout=stdout.strip(),
                stderr=stderr.strip(),
                executed=True,
                test_results=[TestCaseResult(name=tc.name, passed=False, actual_output=None) for tc in test_cases],
            )

        console_out, _, results_blob = stdout.partition(_RESULTS_SENTINEL)
        try:
            parsed = json.loads(results_blob.strip())
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict) and "import_error" in parsed:
            return CodeExecutionResult(
                stdout=console_out.strip(),
                stderr=(stderr.strip() + "\n" if stderr.strip() else "") + parsed["import_error"],
                executed=True,
                test_results=[TestCaseResult(name=tc.name, passed=False, actual_output=None) for tc in test_cases],
            )

        if not isinstance(parsed, list):
            return CodeExecutionResult(
                stdout=console_out.strip(),
                stderr=stderr.strip() or "Could not parse execution results.",
                executed=True,
                test_results=[TestCaseResult(name=tc.name, passed=False, actual_output=None) for tc in test_cases],
            )

        test_results = [
            TestCaseResult(
                name=r["name"],
                passed=r["passed"],
                actual_output=r["error"] if r.get("error") else json.dumps(r.get("actual")),
            )
            for r in parsed
        ]
        return CodeExecutionResult(
            stdout=console_out.strip() or "(no output)",
            stderr=stderr.strip(),
            executed=True,
            test_results=test_results,
        )


def get_execution_provider() -> CodeExecutionProvider:
    """Provider selection point, mirroring apps/api/orchestrator.get_gateway().
    Real execution for Python via subprocess (see PythonSubprocessExecutionProvider's
    docstring for the security caveat); every other language still gets the
    honest mock "not executed" response until it has real execution too."""

    return PythonSubprocessExecutionProvider()
