// Shared level/status helpers for the world-model UI (specs/005). Level order
// and labels mirror rubrics/competencies/v1.yaml; colors are the app's own
// status tokens (globals.css), so light and dark mode come for free.
import type { WMNodeStatus } from "@/lib/api";

export const LEVEL_LABELS = ["Below Senior", "Senior", "Staff", "Principal"];
export const LEVEL_KEYS = ["below_senior", "senior", "staff", "principal"];

export function levelLabel(key: string | null | undefined): string {
  const i = key ? LEVEL_KEYS.indexOf(key) : -1;
  return i >= 0 ? LEVEL_LABELS[i] : "Not enough evidence";
}

// Nearest level name for an expected level on the 0-3 scale.
export function meanLabel(mean: number): string {
  return LEVEL_LABELS[Math.max(0, Math.min(3, Math.round(mean)))];
}

export const STATUS_COLOR: Record<WMNodeStatus, string> = {
  strong: "var(--color-status-strong-positive)",
  thin: "var(--color-status-neutral)",
  wrong: "var(--color-status-strong-concern)",
  none: "var(--color-muted-foreground)",
};

export const STATUS_TEXT: Record<WMNodeStatus, string> = {
  strong: "strong evidence",
  thin: "thin evidence",
  wrong: "went wrong",
  none: "no evidence here",
};
