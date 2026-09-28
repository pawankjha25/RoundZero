// Canonical round-type list: key, display label, default duration, and
// whether it has a real interviewer today. Single source of truth for the
// 7 round types shown in RoundTypeIcon.tsx - previously duplicated (with
// slightly different shapes) across app/loop-planner/page.tsx and
// app/practice/page.tsx; also used by the new loop builder
// (app/loops/new/page.tsx). Only "available: true" round types can actually
// be started (apps/api/orchestrator.py::REAL_ROUND_TYPES is the backend's
// own copy of this same allowlist, kept in sync by hand) - every other type
// can still be planned into a loop, it just can't be started yet. Only
// "hiring_manager" remains coming-soon as of 2026-09-05 (Backend System
// Design, Technical Leadership, and Cross-functional all shipped real
// interviewers that day).
import type { RoundTypeKey } from "@/components/RoundTypeIcon";

export interface RoundTypeMeta {
  key: RoundTypeKey;
  label: string;
  duration: number;
  available: boolean;
}

export const ROUND_TYPES: RoundTypeMeta[] = [
  { key: "ml_system_design", label: "ML System Design", duration: 60, available: true },
  { key: "coding", label: "Coding", duration: 50, available: true },
  { key: "backend_system_design", label: "Backend System Design", duration: 60, available: true },
  { key: "ml_depth", label: "ML Depth", duration: 60, available: true },
  { key: "technical_leadership", label: "Technical Leadership", duration: 50, available: true },
  { key: "xfn", label: "Cross-functional", duration: 45, available: true },
  { key: "hiring_manager", label: "Hiring Manager", duration: 45, available: false },
];
