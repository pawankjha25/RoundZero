// Small shared formatters - split out of app/dashboard/page.tsx so
// app/loops/page.tsx and app/progress/page.tsx (specs/003-premium-uiux-
// redesign IA update: My Loops split out of Home, Report renamed to
// Progress) can reuse the exact same slug/status formatting instead of each
// keeping its own copy.
//
// Some slug words are abbreviations, not ordinary words - naive
// `w[0].toUpperCase() + w.slice(1)` capitalization leaves the rest of the
// word lowercase, so "ml" becomes "Ml". That lowercase "l" is visually
// indistinguishable from a capital "I" in every sans-serif UI font (neither
// has a foot/serif), so "Ml Engineer"/"Ml System Design" reads as "MI
// Engineer"/"MI System Design" - a real text bug, not a font-rendering one
// (see apps/api/orchestrator.py::_LABEL_WORD_OVERRIDES for the same fix on
// the backend's own loop-name deriving code). Extend this map if a future
// slug introduces another all-caps abbreviation.
const WORD_OVERRIDES: Record<string, string> = { ml: "ML" };

export function formatLabel(slug: string): string {
  return slug
    .split("_")
    .map((w) => WORD_OVERRIDES[w] ?? w[0].toUpperCase() + w.slice(1))
    .join(" ");
}
