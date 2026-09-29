"use client";

// Chart components for /progress (2026-09 "make progress a real diagnostic
// report" request - charts/graphs, per-subarea (dimension) breakdowns, and
// a plain-language diagnosis, not just the previous stat tiles + a text-only
// "N -> M" trend list).
//
// Chart form choices follow the dataviz skill:
//  - Readiness-over-time is a single series (one candidate's own readiness
//    %) -> sequential/one-hue (the app's own --color-accent), never a
//    generated categorical color, with each point additionally colored by
//    hire-signal tone as a secondary encoding (dot fill only, always paired
//    with the tooltip's text label - color is never the only signal).
//  - Per-dimension trends do NOT share one multi-line chart: rubrics run
//    6-10 dimensions (rubrics/*/v1.yaml), well past the categorical
//    series-count ceiling for an all-pairs form. Each dimension instead
//    gets its own "stat tile + sparkline" (dataviz's prescribed form for "a
//    single current value + trend") - small multiples, one hue each, no
//    categorical-identity problem at all.
//  - Hire-signal mix and the weakest-dimensions bar are magnitude/count
//    comparisons -> bar charts, one hue (or the app's own 5-step status
//    scale for hire signal specifically, since that's fixed, already
//    shipped, and semantically tied to signal severity rather than
//    arbitrary category identity).
// All colors are the app's own CSS custom properties (--color-accent,
// --color-status-*, --color-border, --color-muted-foreground) referenced as
// var(...) strings passed straight into recharts' stroke/fill props - SVG
// presentation attributes resolve CSS custom properties like any other CSS
// value, so both light and dark mode come from the one set of tokens
// globals.css already defines, with no separate chart palette to maintain.
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipContentProps } from "recharts";
import { HIRE_SIGNAL_THRESHOLDS, hireSignalTone, toneColorVar } from "@/lib/status";
import type { WeakDimension } from "@/lib/api";

const ACCENT = "var(--color-accent)";
const MUTED = "var(--color-muted-foreground)";
const BORDER = "var(--color-border)";
const SURFACE = "var(--color-surface)";
const SUCCESS = "var(--color-status-strong-positive)";
const CONCERN = "var(--color-status-strong-concern)";

export function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// --- Readiness over time ---------------------------------------------------

export interface ReadinessPoint {
  id: string;
  label: string;
  pct: number;
  hireSignal: string;
  roundTypeLabel: string;
  // Raw round_type key (e.g. "ml_system_design"), kept alongside the
  // display label so callers can group/compare points by round type
  // (see app/progress/page.tsx's buildDiagnosis - RZ-12 fix).
  roundType: string;
}

function ReadinessTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || !payload.length) return null;
  const point = payload[0].payload as ReadinessPoint;
  const tone = hireSignalTone(point.hireSignal);
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2 text-sm shadow-sm">
      <p className="text-lg font-semibold leading-tight text-foreground">{point.pct}%</p>
      <p className="mt-0.5 text-xs text-muted-foreground">
        {point.roundTypeLabel} &middot; {point.label}
      </p>
      <p className="mt-1 text-xs font-semibold" style={{ color: toneColorVar(tone) }}>
        {point.hireSignal}
      </p>
    </div>
  );
}

interface ReadinessDotProps {
  cx?: number;
  cy?: number;
  payload?: ReadinessPoint;
}

function ReadinessDot({ cx, cy, payload }: ReadinessDotProps) {
  if (cx === undefined || cy === undefined || !payload) return null;
  const tone = hireSignalTone(payload.hireSignal);
  return (
    <circle
      cx={cx}
      cy={cy}
      r={4}
      fill={toneColorVar(tone)}
      stroke={SURFACE}
      strokeWidth={1.5}
    />
  );
}

export function ReadinessTrendChart({ points }: { points: ReadinessPoint[] }) {
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={BORDER} strokeOpacity={0.4} />
          <XAxis
            dataKey="label"
            tick={{ fill: MUTED, fontSize: 11 }}
            axisLine={{ stroke: BORDER }}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tick={{ fill: MUTED, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <RechartsTooltip content={ReadinessTooltip} cursor={{ stroke: BORDER, strokeDasharray: "3 3" }} />
          <Line
            type="monotone"
            dataKey="pct"
            stroke={ACCENT}
            strokeWidth={2}
            dot={<ReadinessDot />}
            activeDot={{ r: 6 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// --- Hire-signal mix --------------------------------------------------------

interface SignalCountRow {
  signal: string;
  count: number;
}

function SignalTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || !payload.length) return null;
  const row = payload[0].payload as SignalCountRow;
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2 text-sm shadow-sm">
      <p className="text-lg font-semibold leading-tight text-foreground">{row.count}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{row.signal}</p>
    </div>
  );
}

export function HireSignalMixChart({ signals }: { signals: string[] }) {
  const rows: SignalCountRow[] = HIRE_SIGNAL_THRESHOLDS.map(([, signal]) => ({
    signal,
    count: signals.filter((s) => s === signal).length,
  }));
  const height = rows.length * 34 + 8;
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 24, left: 0, bottom: 0 }}>
          <XAxis type="number" hide domain={[0, "dataMax"]} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="signal"
            tick={{ fill: MUTED, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={110}
          />
          <RechartsTooltip content={SignalTooltip} cursor={{ fill: "var(--color-muted)" }} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={16} isAnimationActive={false} label={{ position: "right", fill: MUTED, fontSize: 12 }}>
            {rows.map((row) => (
              <Cell key={row.signal} fill={toneColorVar(hireSignalTone(row.signal))} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// --- Per-dimension stat tile (value + delta + sparkline) -------------------

export function DimensionStatTile({ label, scores }: { label: string; scores: number[] }) {
  const latest = scores[scores.length - 1];
  const first = scores[0];
  const delta = latest - first;
  const deltaColor = delta > 0 ? SUCCESS : delta < 0 ? CONCERN : MUTED;
  const deltaText = delta > 0 ? `+${delta}` : delta < 0 ? `${delta}` : "flat";
  const data = scores.map((score, i) => ({ i, score }));

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="shrink-0 text-xs font-semibold" style={{ color: deltaColor }}>
          {scores.length > 1 ? deltaText : ""}
        </p>
      </div>
      <p className="mt-1 text-xl font-semibold text-foreground">
        {latest}
        <span className="text-sm font-normal text-muted-foreground">/4</span>
      </p>
      <div className="mt-2 h-10 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            <YAxis domain={[0.5, 4.5]} hide />
            <Line
              type="monotone"
              dataKey="score"
              stroke={ACCENT}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// --- Weakest dimensions (most recent evaluated round) -----------------------

function WeakestTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || !payload.length) return null;
  const row = payload[0].payload as WeakDimension;
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2 text-sm shadow-sm">
      <p className="text-lg font-semibold leading-tight text-foreground">{row.score}/4</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{row.label}</p>
    </div>
  );
}

export function WeakestDimensionsChart({ weakest }: { weakest: WeakDimension[] }) {
  const height = weakest.length * 34 + 8;
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={weakest} layout="vertical" margin={{ top: 0, right: 24, left: 0, bottom: 0 }}>
          <XAxis type="number" hide domain={[0, 4]} />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fill: MUTED, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={160}
          />
          <RechartsTooltip content={WeakestTooltip} cursor={{ fill: "var(--color-muted)" }} />
          <Bar dataKey="score" fill={ACCENT} radius={[0, 4, 4, 0]} maxBarSize={16} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
