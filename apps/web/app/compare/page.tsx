"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { compareRounds, me, type HistoryItem, type RoundComparison, type User } from "@/lib/api";
import { formatLabel } from "@/lib/format";
import { ROUND_TYPES } from "@/lib/roundTypes";

const ROUND_TYPE_LABELS = new Map(ROUND_TYPES.map((rt) => [rt.key, rt.label]));

// RZ-10 (UI/UX review, 2026-09-29): the old heading built its "X vs Y" line
// entirely from round_older's own level/role_family, so comparing two rounds
// with different targets (or different round types) silently hid that
// mismatch - "Staff ML Engineer - 9/26 vs. 9/29" even when 9/29 was an Entry
// Level Coding round. Each side now states its own identity.
function roundIdentity(round: HistoryItem): string {
  const typeLabel =
    ROUND_TYPE_LABELS.get(round.round_type as (typeof ROUND_TYPES)[number]["key"]) ?? formatLabel(round.round_type);
  return `${typeLabel} - ${formatLabel(round.level)} ${formatLabel(round.role_family)}`;
}

function deltaBadge(delta: number, suffix = "") {
  if (delta === 0) {
    return <span className="text-muted-foreground">no change</span>;
  }
  const positive = delta > 0;
  return (
    <span className={positive ? "font-medium text-status-strong-positive" : "font-medium text-status-strong-concern"}>
      {positive ? "+" : ""}
      {delta}
      {suffix}
    </span>
  );
}

function ComparePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roundIdA = searchParams.get("a");
  const roundIdB = searchParams.get("b");

  const [user, setUser] = useState<User | null>(null);
  const [comparison, setComparison] = useState<RoundComparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  // Missing query params isn't something that happens after a render - it's
  // knowable from the params themselves, so it's derived here instead of
  // being pushed into state from inside the effect below (which used to
  // call setError synchronously on the very first effect run for this case -
  // a react-hooks/set-state-in-effect violation, and functionally a diff
  // update squeezed into an extra render for no reason).
  const missingParamsMessage = !roundIdA || !roundIdB ? "Pick two rounds from your dashboard to compare." : null;

  useEffect(() => {
    if (!roundIdA || !roundIdB) {
      return;
    }
    let cancelled = false;
    compareRounds(roundIdA, roundIdB)
      .then((c) => {
        if (!cancelled) setComparison(c);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load comparison");
      });
    return () => {
      cancelled = true;
    };
  }, [roundIdA, roundIdB]);

  const displayError = error ?? missingParamsMessage;
  if (displayError) {
    return (
      <AppShell user={user} active="loops">
        <div className="mx-auto max-w-2xl">
          <p className="text-sm text-status-strong-concern">{displayError}</p>
          <Link href="/dashboard" className="mt-4 inline-block text-sm text-muted-foreground underline">
            Back to dashboard
          </Link>
        </div>
      </AppShell>
    );
  }

  if (!comparison) {
    return (
      <AppShell user={user} active="loops">
        <p className="text-sm text-muted-foreground">Loading comparison...</p>
      </AppShell>
    );
  }

  const { round_older, round_newer, evaluation_older, evaluation_newer, dimension_deltas } = comparison;
  const deltasByDim = new Map(dimension_deltas.map((d) => [d.dimension, d]));
  const sortedDims = [...evaluation_newer.dimension_scores].sort((a, b) => b.weight - a.weight);

  return (
    <AppShell user={user} active="loops">
      <div className="mx-auto max-w-2xl space-y-8">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Compare rounds</h1>
          <p className="mt-1 text-base text-muted-foreground">
            {new Date(round_older.created_at).toLocaleDateString()} vs.{" "}
            {new Date(round_newer.created_at).toLocaleDateString()}
          </p>
          {(round_older.round_type !== round_newer.round_type || round_older.level !== round_newer.level) && (
            <p className="mt-2 rounded-md border border-dashed border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              These two rounds aren&apos;t directly comparable - {roundIdentity(round_older)} vs. {roundIdentity(round_newer)}.
              A readiness change here may reflect the different round type or level, not just performance.
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-lg border border-border bg-surface p-5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Earlier - {new Date(round_older.created_at).toLocaleDateString()}
            </p>
            <p className="mt-1 text-sm font-medium text-foreground">{roundIdentity(round_older)}</p>
            <p className="mt-2 text-2xl font-semibold text-foreground">{evaluation_older.readiness_pct}%</p>
            <p className="mt-1 text-sm text-muted-foreground">{comparison.hire_signal_older}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface p-5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Later - {new Date(round_newer.created_at).toLocaleDateString()}
            </p>
            <p className="mt-1 text-sm font-medium text-foreground">{roundIdentity(round_newer)}</p>
            <p className="mt-2 text-2xl font-semibold text-foreground">
              {evaluation_newer.readiness_pct}% <span className="ml-2 text-base">{deltaBadge(comparison.readiness_delta, "pp")}</span>
            </p>
            <p className="mt-1 text-sm text-muted-foreground">{comparison.hire_signal_newer}</p>
          </div>
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold text-foreground">Dimension-by-dimension</h2>
          <div className="space-y-3">
            {sortedDims.map((d) => {
              const delta = deltasByDim.get(d.dimension);
              return (
                <div key={d.dimension} className="rounded-lg border border-border bg-surface p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground">{d.label}</p>
                    <p className="text-sm text-muted-foreground">
                      {delta ? (
                        <>
                          {delta.score_older}/4 → {delta.score_newer}/4{" "}
                          <span className="ml-1">{deltaBadge(delta.delta)}</span>
                        </>
                      ) : (
                        `${d.score}/4`
                      )}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex gap-4 text-sm">
          <Link href={`/reports/${round_older.id}`} className="text-muted-foreground underline">
            View earlier report
          </Link>
          <Link href={`/reports/${round_newer.id}`} className="text-muted-foreground underline">
            View later report
          </Link>
        </div>
      </div>
    </AppShell>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={null}>
      <ComparePageContent />
    </Suspense>
  );
}
