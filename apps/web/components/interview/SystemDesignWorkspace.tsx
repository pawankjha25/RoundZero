"use client";

// Split-screen system design workspace: AIInterviewerPanel on the left, an
// Excalidraw whiteboard on the right. Wired into the real, working
// ml_system_design round type (WorkspaceRouter routes ml_system_design and
// backend_system_design here). On every debounced canvas edit, converts the
// scene into a compact semantic summary (lib/workspace/summarizeScene.ts) and
// saves both the raw scene (for reconnect restore) and the summary (for the
// interviewer's context) via saveCanvas - never sends raw drawing events to
// the LLM, per the workspace spec.
import "@excalidraw/excalidraw/index.css";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { getWorkspaceState, saveCanvas } from "@/lib/api";
import { summarizeScene, type SceneElementLike } from "@/lib/workspace/summarizeScene";
import AIInterviewerPanel from "./AIInterviewerPanel";
import type { WorkspaceProps } from "./ConversationalWorkspace";

// Excalidraw touches window/document at module load time - load it client-only
// so Next's server render never tries to evaluate it.
const Excalidraw = dynamic(() => import("@excalidraw/excalidraw").then((mod) => mod.Excalidraw), {
  ssr: false,
});

const SAVE_DEBOUNCE_MS = 2000;

interface SystemDesignWorkspaceProps extends WorkspaceProps {
  roundIdOverride?: string; // used by the /dev/workspaces harness, which has no real round
}

export default function SystemDesignWorkspace(props: SystemDesignWorkspaceProps) {
  const roundId = props.roundIdOverride ?? props.round.id;
  const harness = Boolean(props.roundIdOverride);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [savedSummary, setSavedSummary] = useState<string>("");
  // Latest onChange elements, kept outside React state so "Share now" can
  // read the current canvas synchronously without waiting on a re-render.
  const latestElementsRef = useRef<SceneElementLike[]>([]);
  // "Share diagram" button state - see handleShareNow's docstring for why
  // this exists alongside the debounced autosave below.
  const [shareStatus, setShareStatus] = useState<"idle" | "sharing" | "shared">("idle");
  // Candidate feedback (2026-09-03): "think how to give best drawing
  // experience" - the canvas's default size was already the larger grid
  // column (1.6fr vs the interviewer panel's 1fr) but still cramped for
  // real system-design diagrams. Maximize gives an escape hatch to a true
  // full-viewport canvas (like Excalidraw's/Figma's own fullscreen) rather
  // than permanently stealing screen space from the interviewer panel by
  // default, which "both"/text-mode candidates still need visible.
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    if (!maximized) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setMaximized(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [maximized]);

  // Async initialData restores whatever scene was last autosaved (reconnect
  // support) - Excalidraw calls this once on mount. The harness skips the
  // network call entirely since there's no real round to restore from.
  const initialData = useMemo(
    () => async () => {
      if (harness) return null;
      try {
        const state = await getWorkspaceState(roundId);
        if (state.canvas_scene && state.canvas_scene.length > 0) {
          if (state.canvas_summary) setSavedSummary(state.canvas_summary);
          return { elements: state.canvas_scene as unknown[] } as never;
        }
      } catch {
        // No saved workspace state yet - start from a blank canvas.
      }
      return null;
    },
    [roundId, harness]
  );

  function handleChange(elements: readonly SceneElementLike[]) {
    latestElementsRef.current = elements as SceneElementLike[];
    if (shareStatus === "shared") setShareStatus("idle"); // new edit -> old "Shared" confirmation is stale
    if (harness) return; // harness mode never persists to a real round
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      const summary = summarizeScene(elements as SceneElementLike[]);
      // Skip the network call entirely when nothing meaningful changed
      // (e.g. only a selection or a pan/zoom triggered onChange).
      if (summary === savedSummary) return;
      setSavedSummary(summary);
      saveCanvas(roundId, elements as unknown as Record<string, unknown>[], summary).catch(() => {
        // Best-effort autosave; a transient failure shouldn't interrupt drawing.
      });
    }, SAVE_DEBOUNCE_MS);
  }

  // Explicit "share now" - flushes the debounced autosave immediately
  // instead of waiting SAVE_DEBOUNCE_MS. Added after candidate feedback that
  // the interviewer sometimes answered questions about the diagram against a
  // stale/empty canvas_summary: a live conversation (especially voice) can
  // easily ask "what do you think of this?" faster than the 2s debounce
  // window closes. This doesn't replace the debounced autosave (still runs
  // for reconnect/restore) - it's a deterministic "the interviewer has
  // definitely seen this" moment the candidate can trigger and see confirmed.
  async function handleShareNow() {
    if (harness) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setShareStatus("sharing");
    const elements = latestElementsRef.current;
    const summary = summarizeScene(elements);
    setSavedSummary(summary);
    try {
      await saveCanvas(roundId, elements as unknown as Record<string, unknown>[], summary);
      setShareStatus("shared");
    } catch {
      setShareStatus("idle");
    }
  }

  return (
    <div className="grid w-full grid-cols-1 gap-4 lg:grid-cols-[1fr_1.6fr]">
      <AIInterviewerPanel
        round={props.round}
        transcript={props.transcript}
        setTranscript={props.setTranscript}
        setRound={props.setRound}
        setSecondsLeft={props.setSecondsLeft}
        ending={props.ending}
      />

      <div
        className={
          maximized
            ? "fixed inset-0 z-50 flex flex-col gap-2 bg-background p-4"
            : "flex flex-col gap-2"
        }
      >
        <div className="flex items-center justify-between">
          <p className="text-label font-semibold uppercase tracking-wide text-foreground">System design canvas</p>
          <div className="flex items-center gap-2">
            {!harness && (
              <button
                type="button"
                onClick={handleShareNow}
                disabled={shareStatus === "sharing"}
                className={
                  "rounded-md border px-2.5 py-1 text-xs font-medium disabled:opacity-50 " +
                  (shareStatus === "shared"
                    ? "border-status-positive/40 bg-status-positive-bg text-status-positive"
                    : "border-border text-foreground hover:border-border-strong")
                }
              >
                {shareStatus === "sharing" ? "Sharing..." : shareStatus === "shared" ? "Shared with interviewer" : "Share diagram with interviewer"}
              </button>
            )}
            <button
              type="button"
              onClick={() => setMaximized((m) => !m)}
              title={maximized ? "Exit fullscreen (Esc)" : "Maximize canvas for more drawing room"}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:border-border-strong"
            >
              {maximized ? "Exit fullscreen" : "Maximize"}
            </button>
          </div>
        </div>
        {/* Excalidraw keeps its own light canvas intentionally (better diagram
            readability, specs/003-premium-uiux-redesign section 32) even in
            dark mode - only the frame around it follows the app's theme.
            Default height bumped 75vh -> 82vh (candidate feedback,
            2026-09-03) for more drawing room without a click; maximized mode
            (flex-1 inside the fixed-inset overlay above) goes further and
            fills the full viewport for real diagram work. */}
        <div
          className={
            (maximized ? "flex-1" : "h-[82vh] min-h-[600px]") +
            " overflow-hidden rounded-lg border border-border bg-white"
          }
        >
          <Excalidraw
            initialData={initialData}
            onChange={(elements) => handleChange(elements as unknown as SceneElementLike[])}
          />
        </div>
      </div>
    </div>
  );
}
