"use client";

// Focus Mode shell for every interview round type (specs/003-premium-uiux-
// redesign section 8) - owns the full-height page background itself since
// app/interview/[roundId]/page.tsx no longer wraps this in <AppShell> (no
// app nav during an interview). InterviewHeader (minimal top bar) stays
// constant, WorkspaceRouter swaps in the right panel layout below it.
import type { Dispatch, SetStateAction } from "react";
import type { RoundSummary, Turn } from "@/lib/api";
import EndInterviewTransition from "./EndInterviewTransition";
import InterviewHeader from "./InterviewHeader";
import WorkspaceRouter from "./WorkspaceRouter";

interface InterviewRoomProps {
  round: RoundSummary;
  transcript: Turn[];
  setTranscript: Dispatch<SetStateAction<Turn[]>>;
  setRound: Dispatch<SetStateAction<RoundSummary | null>>;
  secondsLeft: number;
  setSecondsLeft: Dispatch<SetStateAction<number>>;
  ending: boolean;
  endError: string | null;
  onEnd: () => void;
}

export default function InterviewRoom({
  round,
  transcript,
  setTranscript,
  setRound,
  secondsLeft,
  setSecondsLeft,
  ending,
  endError,
  onEnd,
}: InterviewRoomProps) {
  return (
    <div className="min-h-screen bg-background">
      <InterviewHeader round={round} secondsLeft={secondsLeft} ending={ending} onEnd={onEnd} />
      <div className="mx-auto w-full max-w-[1600px] px-5 py-6">
        {ending ? (
          // Replaces the workspace entirely rather than layering a modal on
          // top - unmounting VoiceControls here also cleanly disconnects any
          // live LiveKit room via its own unmount effect, so a voice call
          // doesn't linger while evaluation runs server-side.
          <EndInterviewTransition error={endError} onRetry={onEnd} />
        ) : (
          <WorkspaceRouter
            round={round}
            transcript={transcript}
            setTranscript={setTranscript}
            setRound={setRound}
            setSecondsLeft={setSecondsLeft}
            ending={ending}
          />
        )}
      </div>
    </div>
  );
}
