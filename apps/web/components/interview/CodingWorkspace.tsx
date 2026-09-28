"use client";

// Split-screen coding workspace: AIInterviewerPanel on the left, a
// Monaco-based code panel on the right. Talks to the workspace endpoints
// (apps/api/routes/rounds.py) via getWorkspaceState/saveCode/runCode.
// Python actually executes for real (PythonSubprocessExecutionProvider, see
// src/roundzero/coding/execution.py - not a security sandbox, see its
// docstring); every other language still gets the honest "not executed" mock
// response until it has real execution too (specs/004-coding-round-type
// scoped Python-only execution for v1 - see that spec's Decision log). Either
// way test_results.passed is only ever true/false when code genuinely ran -
// never fabricated. The Run button also surfaces LLM-generated
// interviewer-style code quality feedback (roundzero.coding.feedback),
// independent of whether tests passed.
//
// The problem panel (title/statement/constraints/starter code/test cases)
// comes from props.round.scenario_prompt + scenario_meta - the real scenario
// CodingInterviewer.pick_scenario chose for this round (see
// prompts/interviewers/coding/scenarios.yaml). The hardcoded Two Sum PROBLEM/
// STARTER_CODE below now only back the /dev/workspaces QA harness, which has
// no real round (and so no scenario_meta) to render from - WorkspaceRouter
// routes coding/ml_coding/ai_assisted_coding here for real rounds.
import dynamic from "next/dynamic";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";
import {
  getWorkspaceState,
  runCode,
  saveCode,
  type CodeQualityFeedback,
  type RunCodeResult,
  type TestCaseSpec,
} from "@/lib/api";
import StatusBadge from "@/components/ui/StatusBadge";
import AIInterviewerPanel from "./AIInterviewerPanel";
import type { WorkspaceProps } from "./ConversationalWorkspace";

// Monaco touches `window`/`navigator` at module load time - load it client-only
// so Next's server render never tries to evaluate it.
const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

export type CodingLanguage = "python" | "java" | "cpp" | "javascript";

const LANGUAGES: { value: CodingLanguage; label: string; monacoId: string }[] = [
  { value: "python", label: "Python", monacoId: "python" },
  { value: "java", label: "Java", monacoId: "java" },
  { value: "cpp", label: "C++", monacoId: "cpp" },
  { value: "javascript", label: "JavaScript", monacoId: "javascript" },
];

// Harness-only fallback (Two Sum) - see the module docstring above.
const STARTER_CODE: Record<CodingLanguage, string> = {
  python: "def two_sum(nums, target):\n    # Return indices of the two numbers that add up to target.\n    pass\n",
  java:
    "class Solution {\n    public int[] twoSum(int[] nums, int target) {\n        // Return indices of the two numbers that add up to target.\n        return new int[]{};\n    }\n}\n",
  cpp:
    "#include <vector>\nusing namespace std;\n\nclass Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n        // Return indices of the two numbers that add up to target.\n        return {};\n    }\n};\n",
  javascript:
    "function twoSum(nums, target) {\n  // Return indices of the two numbers that add up to target.\n}\n",
};

const PROBLEM = {
  title: "Two Sum",
  statement:
    "Given an array of integers nums and an integer target, return the indices of the two numbers such that they add up to target.",
  constraints: [
    "Exactly one valid answer exists.",
    "You may not use the same element twice.",
    "2 <= nums.length <= 10^4",
  ],
  // Python entry point the real execution harness calls with json.loads(input)
  // as positional args, comparing the return value to json.loads(expected_output).
  // Other languages don't execute yet, so this is unused for them.
  entryPoint: "two_sum",
  testCases: [
    { name: "example_1", input: JSON.stringify([[2, 7, 11, 15], 9]), expected_output: JSON.stringify([0, 1]) },
    { name: "example_2", input: JSON.stringify([[3, 2, 4], 6]), expected_output: JSON.stringify([1, 2]) },
    { name: "example_3", input: JSON.stringify([[3, 3], 6]), expected_output: JSON.stringify([0, 1]) },
  ],
};

// Only Python gets real starter code from the scenario (scenario_meta.
// starter_code_python - see prompts/interviewers/coding/scenarios.yaml).
// Execution is Python-only for v1 (specs/004-coding-round-type), so the other
// languages get an honest generic stub naming the real entry point rather
// than a second hand-authored solution skeleton per language per scenario.
function genericStarter(lang: CodingLanguage, entryPoint: string): string {
  const name = entryPoint || "solve";
  switch (lang) {
    case "javascript":
      return `function ${name}() {\n  // Not executed yet - only Python runs for real in this round.\n}\n`;
    case "java":
      return `class Solution {\n    // Not executed yet - only Python runs for real in this round.\n    // TODO: implement ${name}\n}\n`;
    case "cpp":
      return `class Solution {\npublic:\n    // Not executed yet - only Python runs for real in this round.\n    // TODO: implement ${name}\n};\n`;
    case "python":
    default:
      return `def ${name}():\n    pass\n`;
  }
}

const SAVE_DEBOUNCE_MS = 1500;

interface CodingWorkspaceProps extends WorkspaceProps {
  roundIdOverride?: string; // used by the /dev/workspaces harness, which has no real round
}

export default function CodingWorkspace(props: CodingWorkspaceProps) {
  const roundId = props.roundIdOverride ?? props.round.id;
  const isHarness = Boolean(props.roundIdOverride);
  const scenarioMeta = props.round.scenario_meta;
  // A real round always has scenario_meta.title (CodingInterviewer.pick_scenario
  // always returns a titled seed - see prompts/interviewers/coding/scenarios.yaml).
  // The harness has no round at all, so scenarioMeta is undefined there.
  const hasRealScenario = !isHarness && Boolean(scenarioMeta?.title);

  const problem = hasRealScenario
    ? {
        title: scenarioMeta!.title as string,
        statement: props.round.scenario_prompt,
        constraints: scenarioMeta!.constraints ?? [],
        entryPoint: scenarioMeta!.entry_point ?? "",
        testCases: (scenarioMeta!.test_cases ?? []) as TestCaseSpec[],
      }
    : PROBLEM;

  function starterCodeFor(lang: CodingLanguage): string {
    if (!hasRealScenario) return STARTER_CODE[lang];
    if (lang === "python" && scenarioMeta?.starter_code_python) return scenarioMeta.starter_code_python;
    return genericStarter(lang, problem.entryPoint);
  }

  const [language, setLanguage] = useState<CodingLanguage>("python");
  const [code, setCode] = useState<string>(() => starterCodeFor("python"));
  const [loaded, setLoaded] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunCodeResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Restore persisted state on mount (reconnect support).
  useEffect(() => {
    let cancelled = false;
    getWorkspaceState(roundId)
      .then((state) => {
        if (cancelled) return;
        const restoredLanguage = (state.code_language as CodingLanguage) || "python";
        const validLanguage = LANGUAGES.some((l) => l.value === restoredLanguage) ? restoredLanguage : "python";
        setLanguage(validLanguage);
        setCode(state.code_text && state.code_text.length > 0 ? state.code_text : starterCodeFor(validLanguage));
      })
      .catch(() => {
        // No workspace state yet (or harness mode with no real round) - starter code stands.
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roundId]);

  // Debounced autosave whenever code or language changes, after initial load.
  useEffect(() => {
    if (!loaded || props.roundIdOverride) return; // harness mode never persists to a real round
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      saveCode(roundId, language, code).catch(() => {
        // Best-effort autosave; a transient failure shouldn't interrupt typing.
      });
    }, SAVE_DEBOUNCE_MS);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [code, language, loaded, roundId, props.roundIdOverride]);

  function handleLanguageChange(next: CodingLanguage) {
    setLanguage(next);
    setCode(starterCodeFor(next));
    setRunResult(null);
  }

  function handleReset() {
    setCode(starterCodeFor(language));
    setRunResult(null);
    setRunError(null);
  }

  async function handleRun() {
    setRunning(true);
    setRunError(null);
    try {
      const result = props.roundIdOverride
        ? await mockHarnessRun(language, code, problem.testCases)
        : await runCode(roundId, language, code, problem.testCases, problem.entryPoint);
      setRunResult(result);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  const monacoLanguage = LANGUAGES.find((l) => l.value === language)?.monacoId ?? "plaintext";
  // Coding editor naturally fits dark mode (specs/003-premium-uiux-redesign
  // section 32) - Monaco has its own theme prop, follow the app's toggle.
  const { resolvedTheme } = useTheme();
  const monacoTheme = resolvedTheme === "dark" ? "vs-dark" : "light";

  return (
    <div className="grid w-full grid-cols-1 gap-4 lg:grid-cols-2">
      <AIInterviewerPanel
        round={props.round}
        transcript={props.transcript}
        setTranscript={props.setTranscript}
        setRound={props.setRound}
        setSecondsLeft={props.setSecondsLeft}
        ending={props.ending}
      />

      <div className="flex flex-col rounded-lg border border-border bg-surface">
        <div className="border-b border-border p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">{problem.title}</h2>
            <select
              value={language}
              onChange={(e) => handleLanguageChange(e.target.value as CodingLanguage)}
              className="rounded-md border border-border bg-surface px-2 py-1 text-sm text-foreground"
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          <p className="mt-2 text-body text-muted-foreground">{problem.statement}</p>
          {problem.constraints.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-sm text-muted-foreground">
              {problem.constraints.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="h-80 border-b border-border">
          <MonacoEditor
            height="100%"
            language={monacoLanguage}
            value={code}
            onChange={(value) => setCode(value ?? "")}
            theme={monacoTheme}
            options={{ minimap: { enabled: false }, fontSize: 13 }}
          />
        </div>

        <div className="flex items-center gap-2 border-b border-border p-3">
          <button
            onClick={handleRun}
            disabled={running}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-foreground hover:opacity-90 disabled:opacity-50"
          >
            {running ? "Running..." : "Run code"}
          </button>
          <button
            onClick={handleReset}
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:border-border-strong"
          >
            Reset
          </button>
        </div>

        <div className="flex-1 space-y-3 overflow-auto p-3">
          {runError && <p className="text-sm text-status-strong-concern">{runError}</p>}

          {runResult && (
            <>
              <div>
                <p className="mb-1 text-label font-semibold uppercase tracking-wide text-foreground">Console output</p>
                <pre className="whitespace-pre-wrap rounded-md bg-muted p-2 text-sm text-foreground/90">
                  {runResult.stdout}
                  {runResult.stderr ? `\n${runResult.stderr}` : ""}
                </pre>
              </div>
              <div>
                <p className="mb-1 text-label font-semibold uppercase tracking-wide text-foreground">Test cases</p>
                <ul className="space-y-1">
                  {runResult.test_results.map((tc) => (
                    <li key={tc.name} className="flex items-center justify-between text-sm">
                      <span className="text-foreground/90">{tc.name}</span>
                      <TestBadge passed={tc.passed} />
                    </li>
                  ))}
                </ul>
              </div>

              {runResult.feedback && <CodeFeedbackPanel feedback={runResult.feedback} />}
            </>
          )}

          {!runResult && !runError && (
            <p className="text-sm text-muted-foreground">Run your code to see output and test results here.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function TestBadge({ passed }: { passed: boolean | null }) {
  if (passed === null) return <StatusBadge label="not run" tone="neutral" />;
  return <StatusBadge label={passed ? "pass" : "fail"} tone={passed ? "positive" : "strong-concern"} />;
}

// LLM-generated interviewer-style read on the code (roundzero.coding.feedback) -
// shown regardless of whether tests passed, since a real interviewer judges
// readability/complexity/edge cases independent of the mechanical pass/fail.
function CodeFeedbackPanel({ feedback }: { feedback: CodeQualityFeedback }) {
  return (
    <div className="rounded-md border border-border bg-muted p-3">
      <p className="mb-1 text-label font-semibold uppercase tracking-wide text-foreground">Interviewer feedback</p>
      <p className="text-body text-foreground/90">{feedback.summary}</p>

      {feedback.strengths.length > 0 && (
        <div className="mt-2">
          <p className="text-label font-semibold uppercase tracking-wide text-status-positive">Strengths</p>
          <ul className="mt-1 list-inside list-disc text-body text-foreground/90">
            {feedback.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {feedback.concerns.length > 0 && (
        <div className="mt-2">
          <p className="text-label font-semibold uppercase tracking-wide text-status-concern">Concerns</p>
          <ul className="mt-1 list-inside list-disc text-body text-foreground/90">
            {feedback.concerns.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {feedback.complexity_note && (
        <p className="mt-2 text-body text-muted-foreground">
          <span className="font-medium text-foreground/90">Complexity: </span>
          {feedback.complexity_note}
        </p>
      )}

      {feedback.interviewer_followup && (
        <p className="mt-2 text-body italic text-muted-foreground">&ldquo;{feedback.interviewer_followup}&rdquo;</p>
      )}
    </div>
  );
}

// Used only by /dev/workspaces (no real round to call the API against) - keeps
// the harness fully local, but returns the exact same honest "not executed"
// shape the real MockCodeExecutionProvider returns, so the harness can't drift
// from what the real endpoint does.
async function mockHarnessRun(
  language: string,
  _code: string,
  testCases: { name: string }[]
): Promise<RunCodeResult> {
  return {
    stdout: `Not executed - no secure code execution sandbox is configured yet for ${language}. This is a mock response (dev harness); your code was not run.`,
    stderr: "",
    executed: false,
    ran_at: new Date().toISOString(),
    test_results: testCases.map((tc) => ({ name: tc.name, passed: null, actual_output: null })),
    feedback: null,
  };
}
