"use client";

// Loop debrief page (specs/002-full-loop-platform P0.6) - the loop's rounds
// plus, once there are 2+ evaluated real rounds, a synthesized Virtual Hiring
// Committee verdict combining them. Linked from LoopList.tsx's expanded card.
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import AIProcessState from "@/components/ui/AIProcessState";
import StatusBadge from "@/components/ui/StatusBadge";
import RoundTypeIcon, { type RoundTypeKey } from "@/components/RoundTypeIcon";
import { formatLabel } from "@/lib/format";
import { hireSignalTone } from "@/lib/status";
import { ROUND_TYPES } from "@/lib/roundTypes";
import {
  generateLoopCommittee,
  getLoop,
  getLoopCommittee,
  me,
  type CommitteeReport,
  type Loop,
  type User,
} from "@/lib/api";

const ROUND_TYPE_LABELS = new Map<string, string>(ROUND_TYPES.map((rt) => [rt.key, rt.label]));

export default function LoopDebriefPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const loopId = params.id;

  const [user, setUser] = useState<User | null>(null);
  const [loop, setLoop] = useState<Loop | null>(null);
  const [loopError, setLoopError] = useState<string | null>(null);

  const [committee, setCommittee] = useState<CommitteeReport | null>(null);
  const [committeeError, setCommitteeError] = useState<string | null>(null);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  useEffect(() => {
    if (!loopId) return;
    getLoop(loopId)
      .then(setLoop)
      .catch((err) => setLoopError(err instanceof Error ? err.message : "Could not load this loop"));
  }, [loopId]);

  const evaluatedRealCount = loop
    ? loop.rounds.filter((r) => r.started !== null && r.started.status === "EVALUATED").length
    : 0;
  const eligible = evaluatedRealCount >= 2;

  useEffect(() => {
    if (!loop || !eligible) return;
    let cancelled = false;
    getLoopCommittee(loop.id)
      .then((c) => {
        if (!cancelled) setCommittee(c);
      })
      .catch(() =>
        generateLoopCommittee(loop.id)
          .then((c) => {
            if (!cancelled) setCommittee(c);
          })
          .catch((err) => {
            if (!cancelled) setCommitteeError(err instanceof Error ? err.message : "Could not build the committee verdict");
          })
      );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loop?.id, eligible]);

  // Derived, not its own state - "loading" is simply "eligible, nothing to
  // show yet, no error". Avoids a synchronous setState at the top of the
  // effect above (react-hooks/set-state-in-effect), and stays correct
  // automatically the instant a retry clears committeeError too.
  const committeeLoading = eligible && !committee && !committeeError;

  if (loopError) {
    return (
      <AppShell user={user} active="loops">
        <div className="mx-auto max-w-2xl py-24 text-center">
          <p className="text-body text-muted-foreground">{loopError}</p>
        </div>
      </AppShell>
    );
  }

  if (!loop) {
    return (
      <AppShell user={user} active="loops">
        <div className="mx-auto max-w-2xl py-24">
          <AIProcessState title="Loading loop" steps={[{ label: "Fetching loop details", status: "active" }]} />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell user={user} active="loops">
      <div className="mx-auto max-w-2xl space-y-8">
        <div>
          <p className="mb-2 text-sm">
            <Link href="/loops" className="text-accent hover:underline">
              &larr; My Loops
            </Link>
          </p>
          <h1 className="text-xl font-semibold text-foreground">{loop.name}</h1>
        </div>

        {/* Committee verdict - only once there's genuinely something to synthesize. */}
        {!eligible ? (
          <div className="rounded-xl border border-dashed border-border bg-surface p-6 text-center">
            <p className="text-body text-muted-foreground">
              Complete at least 2 interviews in this loop to get a combined committee verdict.
              {evaluatedRealCount === 1 && " One down."}
            </p>
          </div>
        ) : committeeError ? (
          <div className="rounded-xl border border-border bg-surface p-6">
            <p className="text-body text-foreground">Your rounds are saved.</p>
            <p className="mt-1 text-body text-muted-foreground">Committee verdict could not be built yet. {committeeError}</p>
            <Button
              onClick={() => {
                setCommitteeError(null);
                generateLoopCommittee(loop.id)
                  .then(setCommittee)
                  .catch((err) => setCommitteeError(err instanceof Error ? err.message : "Could not build the committee verdict"));
              }}
              className="mt-4"
            >
              Retry
            </Button>
          </div>
        ) : committeeLoading || !committee ? (
          <div className="rounded-xl border border-border bg-surface p-6">
            <AIProcessState
              title="Committee verdict"
              steps={[
                { label: "Rounds evaluated", status: "done" },
                { label: "Convening the committee", status: "active" },
              ]}
            />
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-surface p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-label font-semibold uppercase tracking-wide text-foreground">Committee verdict</p>
                <p className="mt-1 text-2xl font-semibold text-foreground">{committee.overall_readiness_pct}% readiness</p>
              </div>
              <div className="flex flex-col items-end gap-1.5">
                <StatusBadge label={committee.overall_hire_signal} tone={hireSignalTone(committee.overall_hire_signal)} />
                <span className="text-xs text-muted-foreground">{committee.confidence} confidence</span>
              </div>
            </div>

            <div className="mt-5 border-t border-border pt-4">
              <p className="text-label font-semibold uppercase tracking-wide text-foreground">The committee&apos;s view</p>
              <p className="mt-1.5 text-body text-foreground">{committee.headline}</p>
            </div>

            <div className="mt-4 border-t border-border pt-4">
              <p className="text-label font-semibold uppercase tracking-wide text-foreground">Level signal</p>
              <p className="mt-1.5 text-body text-foreground">{committee.level_signal}</p>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-4 border-t border-border pt-4">
              <div>
                <p className="mb-2 text-label font-semibold uppercase tracking-wide text-foreground">Strengths</p>
                <ul className="space-y-1 text-body text-foreground">
                  {committee.strengths.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="mb-2 text-label font-semibold uppercase tracking-wide text-foreground">Concerns</p>
                <ul className="space-y-1 text-body text-foreground">
                  {committee.concerns.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </div>
            </div>

            {committee.key_evidence.length > 0 && (
              <div className="mt-4 border-t border-border pt-4">
                <p className="mb-2 text-label font-semibold uppercase tracking-wide text-foreground">Key evidence</p>
                <ul className="space-y-1 text-body text-muted-foreground">
                  {committee.key_evidence.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <div>
          <h2 className="mb-3 text-lg font-semibold text-foreground">Rounds in this loop</h2>
          <div className="space-y-2">
            {loop.rounds.map((round) => {
              const started = round.started;
              const label = ROUND_TYPE_LABELS.get(round.round_type) ?? formatLabel(round.round_type);
              // RZ-02 (UI/UX review, 2026-09-29): EVALUATED with a null
              // readiness_pct means this round was submitted with no
              // candidate responses at all - say so plainly rather than
              // falling through to the generic "Evaluated" label (same fix
              // as components/loops/LoopList.tsx::roundStatusLine).
              const statusLine =
                started === null
                  ? round.startable
                    ? "Not started"
                    : "Not available yet"
                  : started.status === "EVALUATED"
                    ? started.readiness_pct !== null
                      ? `${started.readiness_pct}% readiness - ${started.hire_signal}`
                      : "Not assessed - no responses submitted"
                    : formatLabel(started.status);
              const href = started
                ? started.status === "ACTIVE" || started.status === "WRAP_UP"
                  ? `/interview/${started.id}`
                  : `/reports/${started.id}`
                : null;
              const row = (
                <>
                  <div className="flex items-center gap-3">
                    <RoundTypeIcon type={round.round_type as RoundTypeKey} className="shrink-0 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium text-foreground">{label}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">{round.duration_minutes} min</p>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground">{statusLine}</p>
                </>
              );
              if (href) {
                return (
                  <Link
                    key={round.id}
                    href={href}
                    className="flex items-center justify-between rounded-md border border-border p-3 hover:border-border-strong"
                  >
                    {row}
                  </Link>
                );
              }
              return (
                <div key={round.id} className="flex items-center justify-between rounded-md border border-dashed border-border p-3 opacity-70">
                  {row}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
