// Shared status/signal vocabulary (specs/003-premium-uiux-redesign Phase 1 -
// "reusable status components", section 31 "Visual System"). Single source
// of truth for hire-signal thresholds/tone so dashboard/report/compare/
// round-result all agree - previously duplicated ad-hoc in
// app/dashboard/page.tsx (see that file's own comment mirroring
// roundzero.evaluation.evaluator.HIRE_SIGNAL_THRESHOLDS).

export const HIRE_SIGNAL_THRESHOLDS: [number, string][] = [
  [80, "STRONG HIRE"],
  [65, "HIRE"],
  [50, "LEAN HIRE"],
  [35, "LEAN NO HIRE"],
  [0, "NO HIRE"],
];

export function hireSignalFor(pct: number): string {
  for (const [threshold, label] of HIRE_SIGNAL_THRESHOLDS) {
    if (pct >= threshold) return label;
  }
  return "NO HIRE";
}

export type StatusTone = "strong-positive" | "positive" | "neutral" | "concern" | "strong-concern";

export function hireSignalTone(signal: string): StatusTone {
  if (signal === "STRONG HIRE") return "strong-positive";
  if (signal === "HIRE") return "positive";
  if (signal === "LEAN HIRE") return "neutral";
  if (signal === "LEAN NO HIRE") return "concern";
  return "strong-concern";
}

// Tailwind utility strings keyed off the design tokens in globals.css
// (--color-status-*). Always pair with a text label, per the spec's "do not
// rely solely on color" accessibility rule - these classes alone are never
// the only signal a component gives.
const TONE_CLASSES: Record<StatusTone, string> = {
  "strong-positive": "border-status-strong-positive/30 bg-status-strong-positive-bg text-status-strong-positive",
  positive: "border-status-positive/30 bg-status-positive-bg text-status-positive",
  neutral: "border-status-neutral/30 bg-status-neutral-bg text-status-neutral",
  concern: "border-status-concern/30 bg-status-concern-bg text-status-concern",
  "strong-concern": "border-status-strong-concern/30 bg-status-strong-concern-bg text-status-strong-concern",
};

export function toneClasses(tone: StatusTone): string {
  return TONE_CLASSES[tone];
}

// CSS custom-property references (not raw hex) for the same five tones, for
// contexts that need an actual paintable color value rather than a Tailwind
// class string - chiefly SVG chart marks (Progress's readiness trend dots,
// hire-signal distribution bars; see components/ProgressCharts.tsx). SVG
// presentation attributes (stroke/fill) resolve CSS custom properties like
// any other CSS value, so passing e.g. "var(--color-status-positive)"
// straight into a recharts `fill`/`stroke` prop picks up both themes for
// free from the same tokens StatusBadge already uses - no separate light/
// dark chart palette to keep in sync.
const TONE_COLOR_VARS: Record<StatusTone, string> = {
  "strong-positive": "var(--color-status-strong-positive)",
  positive: "var(--color-status-positive)",
  neutral: "var(--color-status-neutral)",
  concern: "var(--color-status-concern)",
  "strong-concern": "var(--color-status-strong-concern)",
};

export function toneColorVar(tone: StatusTone): string {
  return TONE_COLOR_VARS[tone];
}
