"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import AIProcessState from "@/components/ui/AIProcessState";
import StatusBadge from "@/components/ui/StatusBadge";
import EvidenceDrawer from "@/components/report/EvidenceDrawer";
import WorldModelSection from "@/components/worldmodel/WorldModelSection";
import { hireSignalTone } from "@/lib/status";
import { formatLabel } from "@/lib/format";
import {
  getReport,
  getRound,
  me,
  startDrill,
  submitRound,
  type DimensionScore,
  type RoundEvaluation,
  type Turn,
  type User,
} from "@/lib/api";

function formatDim(dim: string): string {
  return dim
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

export default function ReportPage() {
  const router = useRouter();
  const params = useParams<{ roundId: string }>();
  const roundId = params.roundId;

  const [user, setUser] = useState<User | null>(null);
  const [report, setReport] = useState<RoundEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Evidence Drawer state - transcript is fetched lazily, only once a
  // dimension is actually opened, so a normal report view doesn't pay for a
  // second request it may never need.
  const [selectedDim, setSelectedDim] = useState<DimensionScore | null>(null);
  const [transcript, setTranscript] = useState<Turn[] | null>(null);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [drillingPriority, setDrillingPriority] = useState<number | null>(null);
  const [drillError, setDrillError] = useState<string | null>(null);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  useEffect(() => {
    if (!roundId) return;
    let cancelled = false;

    async function load() {
      try {
        const r = await getReport(roundId);
        if (!cancelled) setReport(r);
      } catch {
        try {
          const detail = await getRound(roundId);
          if (detail.round.status === "ACTIVE" || detail.round.status === "WRAP_UP") {
            router.replace(`/interview/${roundId}`);
            return;
          }
          // Submitted but not yet evaluated (shouldn't normally happen - submit
          // evaluates synchronously - but resilient to a partial prior request,
          // e.g. a page refresh mid-evaluation).
          const r = await submitRound(roundId);
          if (!cancelled) setReport(r);
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : "Could not load report");
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [roundId, router]);

  function openEvidence(dim: DimensionScore) {
    setSelectedDim(dim);
    if (!transcript && !transcriptLoading) {
      setTranscriptLoading(true);
      getRound(roundId)
        .then((detail) => setTranscript(detail.transcript))
        .catch(() => setTranscript([]))
        .finally(() => setTranscriptLoading(false));
    }
  }

  async function practiceThis(priority: number) {
    setDrillError(null);
    setDrillingPriority(priority);
    try {
      const detail = await startDrill(roundId, priority);
      router.push(`/interview/${detail.round.id}`);
    } catch (err) {
      setDrillError(err instanceof Error ? err.message : "Could not start a practice round");
      setDrillingPriority(null);
    }
  }

  if (error) {
    return (
      <AppShell user={user}>
        <div className="mx-auto max-w-md py-24 text-center">
          <p className="text-body font-medium text-foreground">Your interview was saved successfully.</p>
          <p className="mt-1 text-body text-muted-foreground">Evaluation could not be completed yet. {error}</p>
          <Button
            onClick={() => {
              setError(null);
              submitRound(roundId)
                .then(setReport)
                .catch((err) => setError(err instanceof Error ? err.message : "Could not load report"));
            }}
            className="mt-5"
            size="large"
          >
            Retry Evaluation
          </Button>
        </div>
      </AppShell>
    );
  }

  if (!report) {
    return (
      <AppShell user={user}>
        <div className="mx-auto max-w-md py-24">
          <AIProcessState
            title="Preparing your report"
            steps={[
              { label: "Transcript received", status: "done" },
              { label: "Evaluating your interview", status: "active" },
            ]}
          />
        </div>
      </AppShell>
    );
  }

  // RZ-02 (UI/UX review, 2026-09-29): a round submitted with no candidate
  // responses at all used to render exactly like a genuine, thorough
  // failure - "0% readiness / NO HIRE" - because the evaluator scored every
  // rubric dimension NOT_COVERED against an empty transcript. The backend
  // now flags this case explicitly (RoundEvaluation.not_assessed) instead
  // of fabricating a score, so show that honestly here rather than the
  // normal report layout (whose dimension/strengths/plan sections would
  // otherwise just render as empty and confusing, not obviously "this round
  // wasn't attempted").
  if (report.not_assessed) {
    return (
      <AppShell user={user} active="loops">
        <div className="mx-auto max-w-md py-24 text-center">
          <p className="text-lg font-semibold text-foreground">Not assessed</p>
          <p className="mt-2 text-body text-muted-foreground">
            No responses were submitted before this round ended, so there&apos;s nothing to score - this isn&apos;t
            counted as a failed attempt.
          </p>
          <Link href="/practice" className="mt-6 inline-block text-sm text-accent hover:underline">
            Start a new round &rarr;
          </Link>
        </div>
      </AppShell>
    );
  }

  const sortedDims = [...report.dimension_scores].sort((a, b) => b.weight - a.weight);
  const tone = hireSignalTone(report.hire_signal);

  return (
    <AppShell user={user} active="loops">
      <div className="mx-auto max-w-2xl space-y-8">
        {/* Conclusion first: hire signal, readiness, and the evaluator's own
            narrative, before any per-dimension detail - specs/003 section 14
            ("lead with the conclusion... not 25 metrics"). */}
        <div className="rounded-xl border border-border bg-surface p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-label font-semibold uppercase tracking-wide text-foreground">Interview report</p>
              <p className="mt-1 text-2xl font-semibold text-foreground">{report.readiness_pct}% readiness</p>
            </div>
            <StatusBadge label={report.hire_signal} tone={tone} />
          </div>

          <div className="mt-5 border-t border-border pt-4">
            <p className="text-label font-semibold uppercase tracking-wide text-foreground">The evaluator&apos;s view</p>
            <p className="mt-1.5 text-body text-foreground">{report.primary_concern}</p>
          </div>

          {/* Level Calibration (specs/002 P0.4) - maps this round's own
              readiness_pct/hire_signal onto the app's level ladder rather than
              inventing a new per-level assessment; see roundzero.leveling.
              calibration's docstring for why this is the honest version. */}
          <div className="mt-5 border-t border-border pt-4">
            <p className="text-label font-semibold uppercase tracking-wide text-foreground">Level calibration</p>
            {(report.level_calibration.safe_target ||
              report.level_calibration.competitive_target ||
              report.level_calibration.stretch_target) && (
              <div className="mt-2 flex flex-wrap gap-2">
                {report.level_calibration.safe_target && (
                  <StatusBadge label={`Safe: ${formatLabel(report.level_calibration.safe_target)}`} tone="neutral" />
                )}
                {report.level_calibration.competitive_target && (
                  <StatusBadge
                    label={`Competitive: ${formatLabel(report.level_calibration.competitive_target)}`}
                    tone="positive"
                  />
                )}
                {report.level_calibration.stretch_target && (
                  <StatusBadge
                    label={`Stretch: ${formatLabel(report.level_calibration.stretch_target)}`}
                    tone="strong-positive"
                  />
                )}
              </div>
            )}
            <p className="mt-1.5 text-body text-foreground">{report.level_calibration.narrative}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-lg border border-border bg-surface p-5">
            <p className="mb-2 text-label font-semibold uppercase tracking-wide text-foreground">Strengths</p>
            {report.strengths.length === 0 ? (
              <p className="text-body text-muted-foreground">None reached target level yet.</p>
            ) : (
              <ul className="space-y-1 text-body text-foreground">
                {report.strengths.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-lg border border-border bg-surface p-5">
            <p className="mb-2 text-label font-semibold uppercase tracking-wide text-foreground">Weaknesses</p>
            {report.weaknesses.length === 0 ? (
              <p className="text-body text-muted-foreground">No significant gaps.</p>
            ) : (
              <ul className="space-y-1 text-body text-foreground">
                {report.weaknesses.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* World-model interviewer (specs/005): level read per competency,
            interview path map and answer drawer - post-interview only. */}
        <WorldModelSection roundId={roundId} />

        <div>
          <div className="mb-1 flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-foreground">Dimension-by-dimension</h2>
            <Link href={`/reports/${roundId}/replay`} className="shrink-0 text-sm text-accent hover:underline">
              View interview replay &rarr;
            </Link>
          </div>
          <p className="mb-3 text-sm text-muted-foreground">Click a dimension to see the evidence behind its score.</p>
          <div className="space-y-3">
            {sortedDims.map((d) => (
              <button
                key={d.dimension}
                onClick={() => openEvidence(d)}
                className="block w-full rounded-lg border border-border bg-surface p-5 text-left transition-colors hover:border-border-strong"
              >
                <div className="mb-1 flex items-center justify-between">
                  <p className="text-body font-medium text-foreground">{d.label}</p>
                  <div className="flex items-center gap-2">
                    <p className="text-sm text-muted-foreground">{d.score}/4</p>
                    <span className="text-sm text-accent">View evidence &rarr;</span>
                  </div>
                </div>
                <p className="line-clamp-2 text-body text-muted-foreground">{d.evidence_narrative}</p>
              </button>
            ))}
          </div>
        </div>

        <div>
          <h2 className="mb-3 text-lg font-semibold text-foreground">Improvement plan</h2>
          {drillError && <p className="mb-3 text-sm text-status-strong-concern">{drillError}</p>}
          <ol className="space-y-3">
            {report.improvement_plan.map((item) => (
              <li key={item.dimension} className="rounded-lg border border-border bg-surface p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-label font-semibold uppercase tracking-wide text-foreground">
                      Priority {item.priority} - {formatDim(item.dimension)}
                    </p>
                    <p className="mt-1 text-body text-foreground">{item.recommendation}</p>
                  </div>
                  <Button
                    onClick={() => practiceThis(item.priority)}
                    disabled={drillingPriority !== null}
                    className="shrink-0"
                  >
                    {drillingPriority === item.priority ? "Starting..." : "Practice this"}
                  </Button>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <EvidenceDrawer
        dimension={selectedDim}
        transcript={transcript}
        transcriptLoading={transcriptLoading}
        onClose={() => setSelectedDim(null)}
      />
    </AppShell>
  );
}
