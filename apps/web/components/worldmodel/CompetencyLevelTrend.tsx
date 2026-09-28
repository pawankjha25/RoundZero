"use client";

// Progress page, across sessions (specs/005): the world model's final level
// read per competency for each evaluated round, oldest to newest - so a
// candidate can see whether a gap fixed once stays fixed. Small multiples,
// one hue each (same form as ProgressCharts' DimensionStatTile), plotted on
// the 4-level ladder. Fetches on its own; renders nothing until at least one
// round has world-model data.
import { useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";
import { getCompetencyTrend, type CompetencyTrendPoint } from "@/lib/api";
import { meanLabel } from "./levels";

interface Series {
  competency: string;
  label: string;
  means: number[];
}

export default function CompetencyLevelTrend() {
  const [points, setPoints] = useState<CompetencyTrendPoint[] | null>(null);

  useEffect(() => {
    getCompetencyTrend()
      .then(setPoints)
      .catch(() => setPoints([]));
  }, []);

  if (!points || points.length === 0) return null;

  const byComp = new Map<string, Series>();
  for (const p of points) {
    for (const l of p.levels) {
      if (l.abstained) continue;
      const s = byComp.get(l.competency) ?? { competency: l.competency, label: l.label, means: [] };
      s.means.push(l.mean);
      byComp.set(l.competency, s);
    }
  }
  const series = [...byComp.values()];
  if (series.length === 0) return null;

  return (
    <div className="mb-6 rounded-lg border border-border bg-surface p-4">
      <h2 className="text-sm font-semibold text-foreground">Level by competency</h2>
      <p className="mt-0.5 text-sm text-muted-foreground">
        Where each interview left your level read, oldest to newest. Rounds without enough evidence on a competency are
        skipped.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {series.map((s) => {
          const latest = s.means[s.means.length - 1];
          const delta = s.means.length > 1 ? latest - s.means[0] : 0;
          return (
            <div key={s.competency} className="rounded-lg border border-border bg-surface p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-foreground">{s.label}</p>
                {s.means.length > 1 && Math.abs(delta) >= 0.1 && (
                  <p
                    className="shrink-0 text-xs font-semibold"
                    style={{
                      color: delta > 0 ? "var(--color-status-strong-positive)" : "var(--color-status-strong-concern)",
                    }}
                  >
                    {delta > 0 ? "up" : "down"}
                  </p>
                )}
              </div>
              <p className="mt-1 text-lg font-semibold text-foreground">{meanLabel(latest)}</p>
              <div className="mt-2 h-10 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={s.means.map((mean, i) => ({ i, mean }))} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                    <YAxis domain={[0, 3]} hide />
                    <Line
                      type="monotone"
                      dataKey="mean"
                      stroke="var(--color-accent)"
                      strokeWidth={2}
                      dot={s.means.length < 3}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
