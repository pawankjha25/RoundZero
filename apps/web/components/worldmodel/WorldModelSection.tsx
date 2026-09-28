"use client";

// Report-page section for the world-model interviewer (specs/005): level read
// per competency (only ever shown after the interview - decided 2026-09-28),
// the interview path map, and the answer drawer. Loads independently of the
// main report so a world-model hiccup never blocks the evaluation view.
import { useEffect, useMemo, useState } from "react";
import {
  createFlipRewrites,
  createRetry,
  getWorldModel,
  type WMCompetencyDiagnosis,
  type WorldModelReport,
} from "@/lib/api";
import AnswerDrawer from "./AnswerDrawer";
import PathMap from "./PathMap";
import { STATUS_COLOR, levelLabel } from "./levels";

function pickDefaultTurn(d: WMCompetencyDiagnosis): number | null {
  if (d.went_wrong_turn != null) return d.went_wrong_turn;
  const withEvidence = d.path.find((p) => p.evidence.length > 0);
  return withEvidence?.turn_index ?? d.path[0]?.turn_index ?? null;
}

export default function WorldModelSection({ roundId }: { roundId: string }) {
  const [report, setReport] = useState<WorldModelReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [competency, setCompetency] = useState<string | null>(null);
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null);
  const [generatingFix, setGeneratingFix] = useState(false);
  const [fixError, setFixError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getWorldModel(roundId)
      .then((r) => {
        if (cancelled) return;
        setReport(r);
        const ranked = [...r.competencies].sort(
          (a, b) => Number(a.abstained) - Number(b.abstained) || (b.causes[0]?.impact ?? 0) - (a.causes[0]?.impact ?? 0),
        );
        const first = ranked[0];
        if (first) {
          setCompetency(first.competency);
          setSelectedTurn(pickDefaultTurn(first));
        }
      })
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Could not load the path map"));
    return () => {
      cancelled = true;
    };
  }, [roundId]);

  const diagnosis = useMemo(
    () => report?.competencies.find((c) => c.competency === competency) ?? null,
    [report, competency],
  );

  if (error) {
    return (
      <div className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
        The interview path map isn&apos;t available for this round. {error}
      </div>
    );
  }
  if (!report) {
    return <div className="rounded-lg border border-border bg-surface p-5 text-sm text-muted-foreground">Loading path map...</div>;
  }
  if (report.competencies.length === 0 || report.answers_total === 0) return null;

  const rewrite = diagnosis ? report.rewrites.find((r) => r.competency === diagnosis.competency) ?? null : null;
  const retry =
    selectedTurn != null ? [...report.retries].reverse().find((r) => r.turn_index === selectedTurn) ?? null : null;
  const latestRetryForMap = diagnosis
    ? [...report.retries].reverse().find((r) => diagnosis.path.some((p) => p.turn_index === r.turn_index)) ?? null
    : null;
  const pointIndex = diagnosis ? diagnosis.path.findIndex((p) => p.turn_index === selectedTurn) : -1;
  const point = diagnosis && pointIndex >= 0 ? diagnosis.path[pointIndex] : null;
  const previousMean =
    diagnosis && pointIndex > 0 ? diagnosis.path[pointIndex - 1].level_mean : point?.level_mean ?? 0;

  async function generateFix() {
    setGeneratingFix(true);
    setFixError(null);
    try {
      const rewrites = await createFlipRewrites(roundId);
      setReport((r) => (r ? { ...r, rewrites } : r));
    } catch (err) {
      setFixError(err instanceof Error ? err.message : "Could not generate the fix");
    } finally {
      setGeneratingFix(false);
    }
  }

  async function retryAnswer(text: string) {
    if (selectedTurn == null) return;
    const result = await createRetry(roundId, selectedTurn, text);
    setReport((r) => (r ? { ...r, retries: [...r.retries, result] } : r));
  }

  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-foreground">Interview path map</h2>
        <p className="text-xs text-muted-foreground">
          {report.answers_processed}/{report.answers_total} answers analyzed
        </p>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        Your level read after every answer, per competency. Click an answer to see what moved it.
      </p>

      <div className="mb-3 flex flex-wrap gap-2" role="tablist" aria-label="Competency">
        {report.competencies.map((c) => {
          const active = c.competency === competency;
          return (
            <button
              key={c.competency}
              role="tab"
              aria-selected={active}
              onClick={() => {
                setCompetency(c.competency);
                setSelectedTurn(pickDefaultTurn(c));
              }}
              className={
                "rounded-full border px-3 py-1 text-sm transition-colors " +
                (active
                  ? "border-accent bg-accent/10 font-medium text-foreground"
                  : "border-border text-muted-foreground hover:border-border-strong")
              }
            >
              {c.label}
              <span className="ml-1.5 text-xs text-muted-foreground">
                {c.abstained ? "not enough evidence" : levelLabel(c.final_level)}
              </span>
            </button>
          );
        })}
      </div>

      {diagnosis && (
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-surface p-4">
            {diagnosis.abstained ? (
              <p className="mb-2 text-sm text-muted-foreground">{diagnosis.abstain_reason}</p>
            ) : (
              <p className="mb-2 text-sm text-foreground">
                <span className="font-semibold">{levelLabel(diagnosis.final_level)}</span> on {diagnosis.label},{" "}
                {Math.round(diagnosis.confidence * 100)}% confidence.
                {diagnosis.causes[0] && (
                  <span className="text-muted-foreground">
                    {" "}
                    Biggest drag: {diagnosis.causes[0].explanation.toLowerCase()} (answer{" "}
                    {diagnosis.path.find((p) => p.turn_index === diagnosis.causes[0].turn_index)?.label}).
                  </span>
                )}
              </p>
            )}
            <PathMap
              diagnosis={diagnosis}
              rewrite={rewrite}
              retry={latestRetryForMap}
              selectedTurn={selectedTurn}
              onSelect={setSelectedTurn}
            />
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              {(["strong", "thin", "wrong"] as const).map((s) => (
                <span key={s} className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLOR[s] }} />
                  {s === "strong" ? "strong evidence" : s === "thin" ? "thin or missing evidence" : "went wrong"}
                </span>
              ))}
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block w-5 border-t-2 border-dashed border-accent" />
                fix, re-scored blind (hypothetical)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block w-5 border-t-2 border-accent" />
                your retry (real)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-5 rounded-sm bg-muted" />
                confidence band
              </span>
            </div>
          </div>

          {fixError && <p className="text-sm text-status-strong-concern">{fixError}</p>}

          {point && (
            <AnswerDrawer
              roundId={roundId}
              point={point}
              previousMean={previousMean}
              causes={diagnosis.causes}
              rewrite={rewrite && rewrite.turn_index === point.turn_index ? rewrite : null}
              retry={retry}
              competencyKey={diagnosis.competency}
              flipAvailable={report.flip_available}
              generatingFix={generatingFix}
              onGenerateFix={generateFix}
              onRetry={retryAnswer}
            />
          )}
        </div>
      )}
    </div>
  );
}
