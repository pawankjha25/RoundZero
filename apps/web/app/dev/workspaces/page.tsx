"use client";

// Manual QA harness for CodingWorkspace and SystemDesignWorkspace - not
// linked from any nav. Renders both workspaces directly against local mock
// round state instead of a real round/API call, letting Monaco and
// Excalidraw be verified mounting and interacting correctly in this app's
// actual Next 16 + Turbopack + client-component setup, without needing a
// live backend round. Both workspace components skip persistence in harness
// mode (roundIdOverride) - the AI interviewer panel is rendered for layout
// parity, but sending a message here will fail since there's no real round
// on the backend; that's expected. scenario_prompt/scenario_meta below are
// empty on purpose - roundIdOverride puts CodingWorkspace in harness mode,
// where it always falls back to its own hardcoded Two Sum placeholder rather
// than reading these (see CodingWorkspace.tsx's hasRealScenario check).
import { useState } from "react";
import CodingWorkspace from "@/components/interview/CodingWorkspace";
import SystemDesignWorkspace from "@/components/interview/SystemDesignWorkspace";
import type { RoundSummary, Turn } from "@/lib/api";

const MOCK_CODING_ROUND: RoundSummary = {
  id: "dev-harness-coding",
  loop_attempt_id: "dev-harness-loop",
  round_type: "coding",
  modality: "text",
  role_family: "ml_engineer",
  level: "mid",
  domain: "general",
  company_profile: "generic",
  duration_minutes: 45,
  status: "ACTIVE",
  phase: "ACTIVE",
  coverage: {},
  time_remaining_sec: 45 * 60,
  created_at: new Date().toISOString(),
  submitted_at: null,
  scenario_prompt: "",
  scenario_meta: {},
};

const MOCK_SYSTEM_DESIGN_ROUND: RoundSummary = {
  ...MOCK_CODING_ROUND,
  id: "dev-harness-system-design",
  round_type: "ml_system_design",
  modality: "text",
};

const MOCK_TRANSCRIPT: Turn[] = [
  { speaker: "interviewer", text: "(dev harness - no real interviewer connected)", phase: "ACTIVE", turn_index: 0 },
];

export default function DevWorkspacesHarnessPage() {
  const [tab, setTab] = useState<"coding" | "system_design">("coding");
  const [codingTranscript, setCodingTranscript] = useState<Turn[]>(MOCK_TRANSCRIPT);
  const [systemDesignTranscript, setSystemDesignTranscript] = useState<Turn[]>(MOCK_TRANSCRIPT);
  const [, setCodingRound] = useState<RoundSummary | null>(MOCK_CODING_ROUND);
  const [, setSystemDesignRound] = useState<RoundSummary | null>(MOCK_SYSTEM_DESIGN_ROUND);
  const [, setSecondsLeft] = useState(MOCK_CODING_ROUND.time_remaining_sec);

  return (
    <div className="min-h-screen bg-muted p-4">
      <div className="mx-auto mb-4 flex w-full max-w-6xl items-center justify-between">
        <div>
          <h1 className="text-sm font-semibold text-foreground">Dev harness: interview workspaces</h1>
          <p className="text-xs text-muted-foreground">
            Local-only QA page - no real round or API persistence. Not linked from navigation.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setTab("coding")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              tab === "coding" ? "bg-accent text-accent-foreground" : "border border-border text-muted-foreground"
            }`}
          >
            Coding
          </button>
          <button
            onClick={() => setTab("system_design")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium ${
              tab === "system_design" ? "bg-accent text-accent-foreground" : "border border-border text-muted-foreground"
            }`}
          >
            System Design
          </button>
        </div>
      </div>

      <div className="mx-auto w-full max-w-6xl">
        {tab === "coding" ? (
          <CodingWorkspace
            round={MOCK_CODING_ROUND}
            roundIdOverride={MOCK_CODING_ROUND.id}
            transcript={codingTranscript}
            setTranscript={setCodingTranscript}
            setRound={setCodingRound}
            setSecondsLeft={setSecondsLeft}
            ending={false}
          />
        ) : (
          <SystemDesignWorkspace
            round={MOCK_SYSTEM_DESIGN_ROUND}
            roundIdOverride={MOCK_SYSTEM_DESIGN_ROUND.id}
            transcript={systemDesignTranscript}
            setTranscript={setSystemDesignTranscript}
            setRound={setSystemDesignRound}
            setSecondsLeft={setSecondsLeft}
            ending={false}
          />
        )}
      </div>
    </div>
  );
}
