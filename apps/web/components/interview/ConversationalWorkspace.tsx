"use client";

// Full-width text interview - today's exact UI/behavior (AIInterviewerPanel at
// the original max-w-2xl centered width), just re-homed under WorkspaceRouter
// so it's the default for any round type without a dedicated workspace.
import type { Dispatch, SetStateAction } from "react";
import type { RoundSummary, Turn } from "@/lib/api";
import AIInterviewerPanel from "./AIInterviewerPanel";

export interface WorkspaceProps {
  round: RoundSummary;
  transcript: Turn[];
  setTranscript: Dispatch<SetStateAction<Turn[]>>;
  setRound: Dispatch<SetStateAction<RoundSummary | null>>;
  setSecondsLeft: Dispatch<SetStateAction<number>>;
  ending: boolean;
}

export default function ConversationalWorkspace(props: WorkspaceProps) {
  return (
    <div className="mx-auto w-full max-w-2xl">
      <AIInterviewerPanel {...props} />
    </div>
  );
}
