"use client";

// Progress (specs/003-premium-uiux-redesign IA update, user-proposed nav) -
// the longitudinal view: "Am I getting better / what level am I at?" Was
// /report; renamed for clarity against /reports/[roundId] (a single round's
// report) which this page is explicitly NOT - and the "Loops" section that
// used to live here was trimmed to a link, since /loops is now the one
// canonical place that list lives (previously duplicated on Home too).
//
// 2026-09 "make progress a real diagnostic report" pass - charts/graphs,
// per-subarea (dimension) breakdowns, and a plain-language diagnosis, not
// just stat tiles and a text-only trend list. Every number on this page is
// still real, already-persisted data (no new backend endpoint, no LLM call
// added): the two new top-of-page charts (readiness over time, hire-signal
// mix) are built entirely from summary.loops, which /v1/report/summary
// already returns per round; "Focus areas" finally renders
// weakest_dimensions/suggested_resources, which report.py has computed and
// returned all along but the frontend never displayed (see that file's
// docstring - the admin UI still curates suggested_resources against it).
// Chart component/color choices are explained in components/ProgressCharts.tsx.
//
// Competency trend is real data (each dimension's actual 1-4 score across
// this candidate's own evaluated ML System Design rounds, oldest to newest -
// note the scale is 1-4, not a percentage), fetched by calling getReport()
// per evaluated round since no aggregate trend endpoint exists yet. Each
// dimension now renders as its own stat-tile + sparkline (dataviz's
// prescribed form for "one current value + trend") instead of a shared
// multi-line chart - rubrics run 6-10 dimensions each (rubrics/*/v1.yaml),
// too many for one legible line chart or a safe categorical palette.
// What's NOT here: a level-calibration boundary bar (blocked on spec 002
// P0.4 - only a single readiness_pct/hire_signal exists today, not a
// calibrated range) and up/down "recent development" arrows on the overall
// diagnosis beyond first-vs-latest (deferred - with only a handful of
// rounds so far, anything fancier would read as more statistically
// confident than it is).
//
// "Next suggested action" (2026-09 redesign) is 3 fixed subsections rather
// than a dynamic weakest-dimension resource list - see apps/api/routes/
// report.py's docstring for why, and apps/web/app/admin/page.tsx's
// SettingsEditor for where each link is set.
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import CompetencyLevelTrend from "@/components/worldmodel/CompetencyLevelTrend";
import AppShell from "@/components/AppShell";
import {
  DimensionStatTile,
  HireSignalMixChart,
  ReadinessTrendChart,
  WeakestDimensionsChart,
  formatShortDate,
  type ReadinessPoint,
} from "@/components/ProgressCharts";
import {
  getReport,
  getReportSummary,
  me,
  type HistoryItem,
  type ReportSummary,
  type User,
} from "@/lib/api";
import { ROUND_TYPES } from "@/lib/roundTypes";

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

// Same label lookup LoopList.tsx uses, so a round type reads the same way
// everywhere in the app (e.g. "ml_system_design" -> "ML System Design").
// Typed <string, ...> rather than <RoundTypeKey, ...> (which ROUND_TYPES'
// own `key` field would otherwise infer) because the round types looked up
// here come from HistoryItem.round_type - a plain string from the API, not
// narrowed to the RoundTypeKey union.
const ROUND_TYPE_LABELS = new Map<string, string>(ROUND_TYPES.map((rt) => [rt.key, rt.label]));
// Canonical display order for trend groups - ROUND_TYPES' own order, not
// whatever order round types happen to appear in the candidate's history.
const ROUND_TYPE_ORDER = new Map<string, number>(ROUND_TYPES.map((rt, i) => [rt.key, i]));

interface DimensionTrend {
  dimension: string;
  label: string;
  scores: number[];
}

interface RoundTypeTrend {
  roundType: string;
  label: string;
  dims: DimensionTrend[];
}

// How many of the candidate's most recent evaluated rounds, PER ROUND TYPE,
// the trend shows - deliberately recent-only by default (not every round
// ever) so the per-dimension score string stays short and the trend reads
// as "how am I doing lately", not a growing wall of numbers as history
// piles up. "Show more" (below) swaps this for TREND_ROUND_LIMIT_EXPANDED
// rather than truly unbounded "all", same reasoning. Applied per round type
// (not globally) since each round type's dimensions are its own rubric
// (rubrics/{round_type}/v1.yaml) - mixing them into one flat list used to
// read as one long, unrelated wall of dimensions (Coding's "Correctness"
// next to ML System Design's "Problem framing").
const TREND_ROUND_LIMIT_DEFAULT = 5;
const TREND_ROUND_LIMIT_EXPANDED = 10;

// Builds the readiness-over-time series from data /v1/report/summary
// already returns per round (HistoryItem.readiness_pct/hire_signal) - no
// extra fetches. A trend needs >=2 points, same rule the per-dimension
// trend below already uses.
function buildReadinessPoints(loops: HistoryItem[]): ReadinessPoint[] {
  return loops
    .filter((r) => r.status === "EVALUATED" && r.readiness_pct !== null && r.hire_signal !== null)
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    .map((r) => ({
      id: r.id,
      label: formatShortDate(r.created_at),
      pct: r.readiness_pct as number,
      hireSignal: r.hire_signal as string,
      roundTypeLabel: ROUND_TYPE_LABELS.get(r.round_type) ?? r.round_type,
    }));
}

// A short, deterministic diagnosis paragraph - no LLM call, just the
// already-computed numbers stated in plain language (same "honest, never
// fabricated" discipline src/roundzero/leveling/calibration.py's narrative
// already follows). Compares oldest vs. newest evaluated round for
// direction, same first-vs-last convention the per-dimension trend arrows
// use, so the two agree with each other rather than using a different
// statistical method that could tell a different story.
function buildDiagnosis(summary: ReportSummary, points: ReadinessPoint[]): string {
  const roundWord = summary.evaluated_rounds === 1 ? "round" : "rounds";
  const loopWord = summary.total_loops === 1 ? "loop" : "loops";
  let text = `You've completed ${summary.evaluated_rounds} evaluated ${roundWord} across ${summary.total_loops} ${loopWord}, averaging ${summary.avg_readiness_pct ?? "-"}% readiness.`;

  if (points.length >= 2) {
    const first = points[0];
    const last = points[points.length - 1];
    const direction = last.pct > first.pct ? "trending up" : last.pct < first.pct ? "trending down" : "holding steady";
    text += ` Your first evaluated round (${first.roundTypeLabel}, ${first.label}) scored ${first.pct}%; your most recent (${last.roundTypeLabel}, ${last.label}) scored ${last.pct}% - ${direction}.`;
  }

  if (summary.weakest_dimensions.length > 0) {
    const top = summary.weakest_dimensions[0];
    text += ` Right now, ${top.label} is your biggest opportunity (${top.score}/4 on your most recent evaluated round) - see Focus areas below.`;
  }

  return text;
}

export default function ProgressPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trends, setTrends] = useState<RoundTypeTrend[] | null>(null);
  const [trendExpanded, setTrendExpanded] = useState(false);

  useEffect(() => {
    me()
      .then((u) => {
        setUser(u);
        getReportSummary()
          .then(setSummary)
          .catch(() => setError("Could not load your report summary."));
      })
      .catch(() => router.push("/login"))
      .finally(() => setChecked(true));
  }, [router]);

  useEffect(() => {
    if (!summary) return;

    const evaluatedByType = new Map<string, HistoryItem[]>();
    for (const r of summary.loops) {
      if (r.status !== "EVALUATED") continue;
      if (!evaluatedByType.has(r.round_type)) evaluatedByType.set(r.round_type, []);
      evaluatedByType.get(r.round_type)!.push(r);
    }

    // Only keep a round type's most recent roundLimit rounds, and
    // only if it has at least 2 (a "trend" needs at least 2 points) - same
    // rule as before, just scoped per round type now instead of globally.
    const roundLimit = trendExpanded ? TREND_ROUND_LIMIT_EXPANDED : TREND_ROUND_LIMIT_DEFAULT;
    const idsByType = new Map<string, string[]>();
    const allIds: string[] = [];
    for (const [roundType, rounds] of evaluatedByType) {
      const ids = rounds
        .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
        .slice(-roundLimit)
        .map((r) => r.id);
      if (ids.length < 2) continue;
      idsByType.set(roundType, ids);
      allIds.push(...ids);
    }
    // No early return for the "nothing to show" case (allIds empty) -
    // Promise.all([]) still resolves via a microtask, so setTrends([]) below
    // runs inside the .then() callback either way, not synchronously in the
    // effect body (react-hooks/set-state-in-effect).

    let cancelled = false;
    Promise.all(
      allIds.map((id) =>
        getReport(id)
          .then((report) => [id, report] as const)
          .catch(() => [id, null] as const)
      )
    ).then((entries) => {
      if (cancelled) return;
      const reportById = new Map(entries);
      const grouped: RoundTypeTrend[] = [];
      for (const [roundType, ids] of idsByType) {
        const byDim = new Map<string, DimensionTrend>();
        for (const id of ids) {
          const report = reportById.get(id);
          if (!report) continue;
          for (const d of report.dimension_scores) {
            if (!byDim.has(d.dimension)) byDim.set(d.dimension, { dimension: d.dimension, label: d.label, scores: [] });
            byDim.get(d.dimension)!.scores.push(d.score);
          }
        }
        if (byDim.size > 0) {
          grouped.push({ roundType, label: ROUND_TYPE_LABELS.get(roundType) ?? roundType, dims: [...byDim.values()] });
        }
      }
      grouped.sort((a, b) => (ROUND_TYPE_ORDER.get(a.roundType) ?? 99) - (ROUND_TYPE_ORDER.get(b.roundType) ?? 99));
      setTrends(grouped);
    });
    return () => {
      cancelled = true;
    };
  }, [summary, trendExpanded]);

  const readinessPoints = useMemo(() => (summary ? buildReadinessPoints(summary.loops) : []), [summary]);
  const diagnosis = useMemo(() => (summary ? buildDiagnosis(summary, readinessPoints) : null), [summary, readinessPoints]);

  if (!checked) {
    return null;
  }

  return (
    <AppShell user={user} active="progress">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-foreground">Progress</h1>
          <p className="mt-1 text-base text-muted-foreground">
            Are you getting better, and what level are you at - across every loop.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-status-strong-concern/30 bg-status-strong-concern-bg p-4 text-sm text-status-strong-concern">
            {error}
          </div>
        )}

        {!summary ? null : summary.total_rounds === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            No interview history yet. Complete a round to see your progress here.
          </div>
        ) : (
          <>
            <div className="mb-6 grid grid-cols-3 gap-3">
              <StatTile label="Loops" value={String(summary.total_loops)} />
              <StatTile label="Rounds evaluated" value={String(summary.evaluated_rounds)} />
              <StatTile
                label="Avg. readiness"
                value={summary.avg_readiness_pct !== null ? `${summary.avg_readiness_pct}%` : "-"}
              />
            </div>

            {summary.latest_hire_signal && (
              <div className="mb-6 rounded-lg border border-border bg-surface p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Latest signal</p>
                <p className="mt-1 text-lg font-semibold text-foreground">
                  {summary.latest_readiness_pct}% - {summary.latest_hire_signal}
                </p>
              </div>
            )}

            {diagnosis && summary.evaluated_rounds > 0 && (
              <div className="mb-6 rounded-lg border border-accent/30 bg-accent/5 p-4">
                <h2 className="text-sm font-semibold text-foreground">Diagnosis</h2>
                <p className="mt-1 text-sm leading-relaxed text-foreground">{diagnosis}</p>
              </div>
            )}

            {readinessPoints.length >= 2 && (
              <div className="mb-6 rounded-lg border border-border bg-surface p-4">
                <h2 className="text-sm font-semibold text-foreground">Readiness over time</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Every evaluated round, oldest to newest, colored by hire signal.
                </p>
                <div className="mt-3">
                  <ReadinessTrendChart points={readinessPoints} />
                </div>
              </div>
            )}

            {readinessPoints.length > 0 && (
              <div className="mb-6 rounded-lg border border-border bg-surface p-4">
                <h2 className="text-sm font-semibold text-foreground">Hire signal mix</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  How your evaluated rounds have landed on the hiring bar, best to worst.
                </p>
                <div className="mt-3">
                  <HireSignalMixChart signals={readinessPoints.map((p) => p.hireSignal)} />
                </div>
              </div>
            )}

            {/* World-model level read per competency across sessions (specs/005). */}
            <CompetencyLevelTrend />

            {trends && trends.length > 0 && (
              <div className="mb-6 rounded-lg border border-border bg-surface p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-foreground">Competency trend</h2>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      Each dimension&apos;s score (1-4) by round type, oldest to newest - your last{" "}
                      {trendExpanded ? TREND_ROUND_LIMIT_EXPANDED : TREND_ROUND_LIMIT_DEFAULT} evaluated rounds of
                      each type.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTrendExpanded((e) => !e)}
                    className="shrink-0 whitespace-nowrap text-sm font-medium text-accent hover:underline"
                  >
                    {trendExpanded ? `Show last ${TREND_ROUND_LIMIT_DEFAULT}` : `Show last ${TREND_ROUND_LIMIT_EXPANDED}`}
                  </button>
                </div>
                <div className="mt-4 space-y-5">
                  {trends.map((group) => (
                    <div key={group.roundType}>
                      <h3 className="text-sm font-semibold text-foreground">{group.label}</h3>
                      <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
                        {group.dims.map((t) => (
                          <DimensionStatTile key={t.dimension} label={t.label} scores={t.scores} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {summary.weakest_dimensions.length > 0 && (
              <div className="mb-6 rounded-lg border border-border bg-surface p-4">
                <h2 className="text-sm font-semibold text-foreground">Focus areas</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Your lowest-scoring dimensions from your most recent evaluated round.
                </p>
                <div className="mt-3">
                  <WeakestDimensionsChart weakest={summary.weakest_dimensions} />
                </div>
                {summary.suggested_resources.length > 0 && (
                  <div className="mt-4 space-y-2 border-t border-border pt-3">
                    {summary.suggested_resources.map((res) => (
                      <div key={res.id} className="text-sm">
                        {res.url ? (
                          <a href={res.url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">
                            {res.title}
                          </a>
                        ) : (
                          <span className="font-medium text-foreground">{res.title}</span>
                        )}
                        {res.note && <span className="text-muted-foreground"> - {res.note}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="mb-8 rounded-lg border border-border bg-surface p-4">
              <h2 className="text-sm font-semibold text-foreground">Next suggested action</h2>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Three ways to keep improving, beyond another round.
              </p>
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-sm font-medium text-foreground">Develop breadth and depth</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Deep dives on ML system design and interviewing.
                  </p>
                  {summary.substack_url ? (
                    <a
                      href={summary.substack_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-3 inline-block rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-foreground hover:opacity-90"
                    >
                      Read the Substack
                    </a>
                  ) : (
                    <p className="mt-3 text-sm text-muted-foreground">Link not set up yet.</p>
                  )}
                </div>

                <div>
                  <p className="text-sm font-medium text-foreground">Develop core competency</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    A structured class covering the fundamentals.
                  </p>
                  {summary.class_url ? (
                    <a
                      href={summary.class_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-3 inline-block rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:border-border-strong"
                    >
                      Join class
                    </a>
                  ) : (
                    <span className="mt-3 inline-block rounded-md border border-dashed border-border px-3 py-1.5 text-sm text-muted-foreground">
                      Coming soon
                    </span>
                  )}
                </div>

                <div>
                  <p className="text-sm font-medium text-foreground">Talk to expert</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Walk through your results and an improvement plan directly with me.
                  </p>
                  {summary.consultancy_url ? (
                    <a
                      href={summary.consultancy_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-3 inline-block rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-foreground hover:opacity-90"
                    >
                      Book a session
                    </a>
                  ) : (
                    <p className="mt-3 text-sm text-muted-foreground">Booking link not set up yet.</p>
                  )}
                </div>
              </div>
            </div>

            <p className="text-sm">
              <Link href="/loops" className="text-accent hover:underline">
                See every loop and round &rarr;
              </Link>
            </p>
          </>
        )}
      </div>
    </AppShell>
  );
}
