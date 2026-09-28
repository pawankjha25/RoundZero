"use client";

// Focus Mode header (specs/003-premium-uiux-redesign section 8 "Interview
// Room - Highest Priority"): minimal, single row - product mark, round type,
// phase, timer, End Round. No app nav, no sidebar, no score/competency
// progress. This is the ONLY chrome rendered during an interview -
// app/interview/[roundId]/page.tsx no longer wraps the round in <AppShell>.
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import type { RoundSummary } from "@/lib/api";
import { ROUND_TYPES } from "@/lib/roundTypes";

export function formatPhase(phase: string): string {
  return phase
    .toLowerCase()
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

// Canonical round-type label lookup (e.g. "xfn" -> "Cross-functional") -
// naive title-casing (the old inline version of this function) happens to
// equal the canonical label for every round type EXCEPT "xfn" (an
// abbreviation, not a normal word - it title-cased to "Xfn"), a bug that
// stayed invisible until this round type shipped a real interviewer
// (2026-09-05) and could actually be reached from this header. Falls back to
// naive title-casing for any round type not in ROUND_TYPES, same as
// LoopList.tsx's identical lookup.
const ROUND_TYPE_LABELS = new Map(ROUND_TYPES.map((rt) => [rt.key, rt.label]));

export function formatRoundType(roundType: string): string {
  return (
    ROUND_TYPE_LABELS.get(roundType as (typeof ROUND_TYPES)[number]["key"]) ??
    roundType
      .split("_")
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join(" ")
  );
}

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, totalSeconds);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

interface InterviewHeaderProps {
  round: RoundSummary;
  secondsLeft: number;
  ending: boolean;
  onEnd: () => void;
}

export default function InterviewHeader({ round, secondsLeft, ending, onEnd }: InterviewHeaderProps) {
  const timeIsLow = secondsLeft <= 120;

  return (
    <header className="flex items-center justify-between gap-4 border-b border-border px-5 py-3">
      <div className="flex items-center gap-3">
        <Link href="/dashboard" className="text-sm font-semibold tracking-tight text-foreground">
          R0
        </Link>
        <span className="hidden text-sm font-medium text-foreground sm:inline">{formatRoundType(round.round_type)}</span>
        <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
          {formatPhase(round.phase)}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span
          className={"font-mono text-sm tabular-nums " + (timeIsLow ? "text-status-strong-concern" : "text-muted-foreground")}
        >
          {formatClock(secondsLeft)}
        </span>
        <ThemeToggle />
        {/* Hidden rather than disabled once ending - the transition screen
            (EndInterviewTransition) owns the only end-of-round action from
            here on, including its own Retry Evaluation button on failure, so
            a second stale "Ending..." control here would be confusing. */}
        {!ending && (
          <button
            onClick={onEnd}
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:border-border-strong"
          >
            End Round
          </button>
        )}
      </div>
    </header>
  );
}
