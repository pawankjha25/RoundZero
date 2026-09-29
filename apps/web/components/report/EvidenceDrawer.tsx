"use client";

// Evidence Drawer (specs/003-premium-uiux-redesign Phase 4, section 15) -
// click-through from a dimension's score to the material behind it.
//
// Built against what's real today, not what section 15 describes end-state:
// the live evaluator (LLMEvaluator, apps/api/orchestrator.py) writes a prose
// evidence_narrative per dimension but currently leaves DimensionScore.evidence
// (the atomic, turn-cited EvidenceItem list - see
// src/roundzero/evaluation/models.py) empty; only the RuleBasedEvaluator
// fallback populates it. So this drawer supports both honestly rather than
// faking the richer case: when evidence[] has real turn-cited items, each one
// is cross-referenced against the round's own transcript and shown inline;
// when it's empty (today's normal path), the drawer says so plainly and
// falls back to the evaluator's narrative plus the full transcript so the
// candidate can check the claim themselves. No fabricated timestamps (turns
// don't carry wall-clock time, only turn_index) and no "Replay Moment" jump
// (blocked on spec 002 P0.9 - no per-timestamp replay data exists yet).
import { useRef } from "react";
import type { DimensionScore, Turn } from "@/lib/api";
import { useOverlayDismiss } from "@/lib/hooks/useOverlayDismiss";

function TurnRow({ turn }: { turn: Turn }) {
  return (
    <div className="rounded-md border border-border bg-muted p-2.5 text-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {turn.speaker === "interviewer" ? "Interviewer" : "You"} · Turn {turn.turn_index}
      </p>
      <p className="mt-1 leading-relaxed text-foreground">{turn.text}</p>
    </div>
  );
}

export default function EvidenceDrawer({
  dimension,
  transcript,
  transcriptLoading,
  onClose,
}: {
  dimension: DimensionScore | null;
  transcript: Turn[] | null;
  transcriptLoading: boolean;
  onClose: () => void;
}) {
  const open = dimension !== null;
  const panelRef = useRef<HTMLDivElement | null>(null);
  useOverlayDismiss(open, onClose, panelRef);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={
          "fixed inset-0 z-40 bg-black/30 transition-opacity " +
          (open ? "opacity-100" : "pointer-events-none opacity-0")
        }
        aria-hidden="true"
      />
      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={dimension ? `Evidence for ${dimension.label}` : "Evidence"}
        className={
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-surface shadow-xl transition-transform " +
          (open ? "translate-x-0" : "translate-x-full")
        }
      >
        {dimension && (
          <>
            <div className="flex items-start justify-between gap-4 border-b border-border p-5">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Evidence</p>
                <h2 className="mt-0.5 text-base font-semibold text-foreground">{dimension.label}</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">{dimension.score}/4</p>
              </div>
              <button
                onClick={onClose}
                className="rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground hover:border-border-strong"
              >
                Close
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Evaluator&apos;s note</p>
              <p className="mt-1.5 text-sm leading-relaxed text-foreground">{dimension.evidence_narrative}</p>

              {dimension.evidence.length > 0 ? (
                <div className="mt-6">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Cited moments
                  </p>
                  <div className="mt-2 space-y-2">
                    {dimension.evidence.map((item, i) => {
                      const turn = transcript?.find((t) => t.turn_index === item.source_turn_index);
                      return (
                        <div key={i} className="rounded-md border border-border p-2.5">
                          <p className="text-sm italic leading-relaxed text-foreground">&ldquo;{item.text}&rdquo;</p>
                          {turn && (
                            <p className="mt-1.5 text-xs text-muted-foreground">
                              Turn {turn.turn_index} · {turn.speaker === "interviewer" ? "Interviewer" : "You"}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="mt-6 rounded-md border border-dashed border-border p-3">
                  <p className="text-sm text-muted-foreground">
                    Citations to the exact moment in the transcript aren&apos;t available for this round yet.
                    Here&apos;s the full transcript so you can check the context yourself.
                  </p>
                </div>
              )}

              <div className="mt-6">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Full transcript</p>
                <div className="mt-2 space-y-2">
                  {transcriptLoading && <p className="text-sm text-muted-foreground">Loading transcript...</p>}
                  {transcript?.map((turn, i) => (
                    <TurnRow key={i} turn={turn} />
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
