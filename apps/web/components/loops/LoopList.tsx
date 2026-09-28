"use client";

// Loop card + classification, rewritten for the real multi-round Loop
// Planner (specs/002 P0.1) - previously grouped a flat HistoryItem[] by
// loop_attempt_id client-side (every loop only ever had one round, since
// nothing created more than one - see the old version's own docstring for
// that history). Now backed directly by GET /v1/loops, which already
// returns each loop's planned rounds (started or not) in one shape.
import { useState } from "react";
import Link from "next/link";
import RoundTypeIcon, { type RoundTypeKey } from "@/components/RoundTypeIcon";
import StatusBadge from "@/components/ui/StatusBadge";
import { formatLabel } from "@/lib/format";
import { hireSignalFor, hireSignalTone } from "@/lib/status";
import { ROUND_TYPES } from "@/lib/roundTypes";
import type { Loop, PlannedRound } from "@/lib/api";

const REAL_ROUND_TYPES = new Set(ROUND_TYPES.filter((rt) => rt.available).map((rt) => rt.key));
// Canonical round-type label lookup (e.g. "xfn" -> "Cross-functional") -
// prefer this over formatLabel(round_type) so round names match exactly
// what the loop builder itself shows, rather than a guessed slug-to-title.
const ROUND_TYPE_LABELS = new Map(ROUND_TYPES.map((rt) => [rt.key, rt.label]));

export type LoopStage = "upcoming" | "ongoing" | "finished";

// Upcoming: created, nothing started yet. Finished: every round of a real,
// startable type has reached EVALUATED - round types with no interviewer
// yet never block this (agreed: "disabled round types don't block
// finished"). Ongoing: everything in between.
export function classifyLoop(loop: Loop): LoopStage {
  const anyStarted = loop.rounds.some((r) => r.started !== null);
  if (!anyStarted) return "upcoming";
  const realRounds = loop.rounds.filter((r) => REAL_ROUND_TYPES.has(r.round_type as RoundTypeKey));
  const allRealDone = realRounds.length > 0 && realRounds.every((r) => r.started?.status === "EVALUATED");
  return allRealDone ? "finished" : "ongoing";
}

export function loopAggregate(loop: Loop): { pct: number; signal: string } | null {
  const evaluated = loop.rounds.map((r) => r.started).filter((h) => h !== null && h.readiness_pct !== null) as NonNullable<
    PlannedRound["started"]
  >[];
  if (evaluated.length === 0) return null;
  if (evaluated.length === 1) {
    return { pct: evaluated[0].readiness_pct!, signal: evaluated[0].hire_signal! };
  }
  const pct = Math.round(evaluated.reduce((sum, r) => sum + r.readiness_pct!, 0) / evaluated.length);
  return { pct, signal: hireSignalFor(pct) };
}

function roundStatusLine(round: PlannedRound): string {
  if (round.started === null) {
    return round.startable ? "Not started" : "Not available yet";
  }
  const h = round.started;
  if (h.status === "EVALUATED" && h.readiness_pct !== null) {
    return `${h.readiness_pct}% readiness - ${h.hire_signal}`;
  }
  if (h.status === "ACTIVE" || h.status === "WRAP_UP") {
    return "In progress";
  }
  return formatLabel(h.status);
}

export function LoopCard({
  loop,
  onStart,
  startingId,
  onDelete,
  deletingId,
  defaultExpanded = false,
  compareMode = false,
  selected = [],
  onToggleCompare,
}: {
  loop: Loop;
  onStart: (loopId: string, plannedRoundId: string) => void;
  startingId: string | null;
  onDelete?: (loopId: string) => void;
  deletingId?: string | null;
  defaultExpanded?: boolean;
  compareMode?: boolean;
  selected?: string[];
  onToggleCompare?: (roundId: string) => void;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded || compareMode);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const aggregate = loopAggregate(loop);
  const primary = loop.rounds[0];
  const startedCount = loop.rounds.filter((r) => r.started !== null).length;

  return (
    <li className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="flex w-full items-center justify-between gap-4 bg-muted px-4 py-3">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
        >
          <span
            aria-hidden="true"
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border-strong text-xs font-medium text-foreground"
          >
            {expanded ? "−" : "+"}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">{loop.name}</p>
            <p className="text-sm text-muted-foreground">
              {primary ? `${formatLabel(primary.level)} ${formatLabel(primary.role_family)} - ` : ""}
              {startedCount} of {loop.rounds.length} interview{loop.rounds.length === 1 ? "" : "s"} started ·{" "}
              {new Date(loop.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
            </p>
          </div>
        </button>
        <div className="flex shrink-0 items-center gap-2">
          {aggregate && (
            <StatusBadge label={`${aggregate.pct}% - ${aggregate.signal}`} tone={hireSignalTone(aggregate.signal)} />
          )}
          {onDelete && !compareMode && (
            confirmingDelete ? (
              <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                <span className="text-xs text-muted-foreground">Delete loop?</span>
                <button
                  type="button"
                  onClick={() => {
                    onDelete(loop.id);
                    setConfirmingDelete(false);
                  }}
                  disabled={deletingId === loop.id}
                  className="rounded-md bg-status-strong-concern px-2 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
                >
                  {deletingId === loop.id ? "Deleting..." : "Delete"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmingDelete(false)}
                  disabled={deletingId === loop.id}
                  className="rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground hover:border-border-strong disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setConfirmingDelete(true);
                }}
                aria-label={`Delete ${loop.name}`}
                title="Delete loop"
                className="rounded-md p-1.5 text-muted-foreground hover:bg-status-strong-concern/10 hover:text-status-strong-concern"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 7h16M9 7V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V7m2 0-.6 12.1A2 2 0 0 1 14.4 21H9.6a2 2 0 0 1-2-1.9L7 7" />
                </svg>
              </button>
            )
          )}
        </div>
      </div>

      {expanded && (
        <div className="space-y-2 p-3">
          {loop.rounds.map((round) => {
            const started = round.started;
            // The startable-and-not-yet-started case needs a real call to
            // action, not just muted status text next to a plain-looking
            // row - the whole row is a <button onClick={onStart}> below,
            // but with only "Not started" in the same muted gray as every
            // other row's status text it read as inert, not clickable
            // (reported: no visible "Start" button on a fresh loop).
            // Matches /setup's own "Start interview" button copy/styling.
            const isReadyToStart = started === null && round.startable && !compareMode;
            const rowInner = (
              <>
                <div className="flex items-center gap-3">
                  <RoundTypeIcon
                    type={round.round_type as RoundTypeKey}
                    className={`shrink-0 ${started || round.startable ? "text-muted-foreground" : "text-muted-foreground/50"}`}
                  />
                  <div>
                    <p className={`text-sm font-medium ${started || round.startable ? "text-foreground" : "text-muted-foreground"}`}>
                      {ROUND_TYPE_LABELS.get(round.round_type as RoundTypeKey) ?? formatLabel(round.round_type)}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{round.duration_minutes} min</p>
                  </div>
                </div>
                {isReadyToStart ? (
                  <span className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-foreground">
                    {startingId === round.id ? "Starting..." : "Start interview"}
                  </span>
                ) : (
                  <p className="text-sm text-muted-foreground">{roundStatusLine(round)}</p>
                )}
              </>
            );

            if (compareMode) {
              const canCompare = started?.status === "EVALUATED";
              const isSelected = started ? selected.includes(started.id) : false;
              return (
                <button
                  key={round.id}
                  type="button"
                  disabled={!canCompare}
                  onClick={() => started && canCompare && onToggleCompare?.(started.id)}
                  className={`flex w-full items-center justify-between rounded-md border p-3 text-left ${
                    !canCompare
                      ? "cursor-not-allowed border-border/60 opacity-50"
                      : isSelected
                        ? "border-accent bg-accent/5"
                        : "border-border hover:border-border-strong"
                  }`}
                >
                  {rowInner}
                </button>
              );
            }

            const href =
              started && (started.status === "ACTIVE" || started.status === "WRAP_UP")
                ? `/interview/${started.id}`
                : started
                  ? `/reports/${started.id}`
                  : null;

            if (href) {
              return (
                <Link
                  key={round.id}
                  href={href}
                  className="flex items-center justify-between rounded-md border border-border p-3 hover:border-border-strong"
                >
                  {rowInner}
                </Link>
              );
            }
            if (round.startable) {
              return (
                <button
                  key={round.id}
                  type="button"
                  disabled={startingId === round.id}
                  onClick={() => onStart(loop.id, round.id)}
                  className="flex w-full items-center justify-between rounded-md border border-border p-3 text-left hover:border-border-strong disabled:opacity-60"
                >
                  {rowInner}
                </button>
              );
            }
            return (
              <div
                key={round.id}
                className="flex cursor-not-allowed items-center justify-between rounded-md border border-dashed border-border p-3 opacity-60"
              >
                {rowInner}
              </div>
            );
          })}
          {!compareMode && startedCount > 0 && (
            <Link
              href={`/loops/${loop.id}`}
              className="block pt-1 text-sm text-accent hover:underline"
            >
              View loop debrief &rarr;
            </Link>
          )}
          {!compareMode && classifyLoop(loop) === "finished" && (
            <Link
              href={`/real-interviews/new?${new URLSearchParams({
                loop_id: loop.id,
                role_family: loop.rounds[0]?.role_family ?? "",
                level: loop.rounds[0]?.level ?? "",
                domain: loop.rounds[0]?.domain ?? "",
              }).toString()}`}
              className="block pt-1 text-sm text-accent hover:underline"
            >
              Log the real interview &rarr;
            </Link>
          )}
        </div>
      )}
    </li>
  );
}
