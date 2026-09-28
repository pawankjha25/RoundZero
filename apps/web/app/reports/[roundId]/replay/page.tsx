"use client";

// Interview Replay (user-requested, from the "keep going for next 5
// features" build sprint) - backlog P0.9's "OK to start with transcript +
// code/canvas timeline before full synced audio replay". A read-only,
// chronological view of everything that happened in a round: chat turns
// interleaved with workspace activity (code edits, test runs, canvas
// updates), each labeled with elapsed time from the round's start.
//
// Deliberately not a literal code/canvas player - WorkspaceEvent rows only
// ever stored light metadata (language, char count, element count), never a
// full snapshot per event (see apps/api/orchestrator.py's
// _workspace_event_summary docstring) - so workspace rows render as short,
// honest summaries ("Ran python (128 chars)"), not a scrubbable diff.
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import { formatLabel } from "@/lib/format";
import { getRound, getRoundTimeline, me, type RoundSummary, type TimelineEvent, type User } from "@/lib/api";

const WORKSPACE_KINDS = new Set(["code_change", "run_attempt", "test_result", "canvas_change"]);

function elapsed(startMs: number, atMs: number): string {
  const totalSec = Math.max(0, Math.round((atMs - startMs) / 1000));
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function ReplayPage() {
  const router = useRouter();
  const params = useParams<{ roundId: string }>();
  const roundId = params.roundId;

  const [user, setUser] = useState<User | null>(null);
  const [round, setRound] = useState<RoundSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  useEffect(() => {
    if (!roundId) return;
    Promise.all([getRound(roundId), getRoundTimeline(roundId)])
      .then(([detail, events]) => {
        setRound(detail.round);
        setTimeline(events);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load the replay"));
  }, [roundId]);

  return (
    <AppShell user={user} active="loops">
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <Link href={`/reports/${roundId}`} className="text-sm text-accent hover:underline">
            &larr; Back to report
          </Link>
          <h1 className="mt-2 text-xl font-semibold text-foreground">Interview replay</h1>
          {round && (
            <p className="mt-1 text-base text-muted-foreground">
              {formatLabel(round.level)} {formatLabel(round.role_family)} - {formatLabel(round.round_type)}
            </p>
          )}
        </div>

        {error && <p className="text-sm text-status-strong-concern">{error}</p>}

        {!error && timeline === null && <p className="text-body text-muted-foreground">Loading...</p>}

        {timeline !== null && timeline.length === 0 && (
          <p className="text-body text-muted-foreground">Nothing was recorded for this round yet.</p>
        )}

        {timeline !== null && timeline.length > 0 && (
          <ol className="space-y-2">
            {(() => {
              const startMs = new Date(timeline[0].created_at).getTime();
              return timeline.map((item, i) => {
                const atMs = new Date(item.created_at).getTime();
                const isWorkspace = WORKSPACE_KINDS.has(item.kind);
                return (
                  <li
                    key={i}
                    className={
                      isWorkspace
                        ? "flex items-start gap-3 rounded-md border border-dashed border-border px-3 py-2"
                        : "flex items-start gap-3 rounded-lg border border-border bg-surface p-4"
                    }
                  >
                    <span className="mt-0.5 shrink-0 font-mono text-xs text-muted-foreground">
                      {elapsed(startMs, atMs)}
                    </span>
                    <div className="min-w-0">
                      {!isWorkspace && (
                        <p className="text-label font-semibold uppercase tracking-wide text-foreground">
                          {item.kind === "turn:interviewer" ? "Interviewer" : "You"}
                        </p>
                      )}
                      <p className={isWorkspace ? "text-sm text-muted-foreground" : "mt-1 text-body text-foreground"}>
                        {item.text}
                      </p>
                    </div>
                  </li>
                );
              });
            })()}
          </ol>
        )}
      </div>
    </AppShell>
  );
}
