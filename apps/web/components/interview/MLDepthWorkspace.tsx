"use client";

// ML Depth workspace: conversational by default (candidate feedback,
// 2026-09-03: "more of conversational rounds") - same centered AIInterviewerPanel
// as ConversationalWorkspace, plus an optional whiteboard toggle for when
// explaining something (e.g. sketching attention heads) is easier drawn than
// typed. Off by default and unmounted when hidden, unlike SystemDesignWorkspace's
// always-on split-screen canvas - this round is talk-first, board-occasional.
// Reuses the exact same saveCanvas/getWorkspaceState endpoints and
// summarizeScene() pipeline SystemDesignWorkspace already uses (round-type-
// agnostic on the backend - see apps/api/orchestrator.py's _workspace_context),
// so MLDepthInterviewer sees the same auto-summarized canvas_summary text
// ML System Design's interviewer does, whenever the candidate has drawn
// something.
import "@excalidraw/excalidraw/index.css";
import dynamic from "next/dynamic";
import { useMemo, useRef, useState } from "react";
import { getWorkspaceState, saveCanvas } from "@/lib/api";
import { summarizeScene, type SceneElementLike } from "@/lib/workspace/summarizeScene";
import AIInterviewerPanel from "./AIInterviewerPanel";
import type { WorkspaceProps } from "./ConversationalWorkspace";

const Excalidraw = dynamic(() => import("@excalidraw/excalidraw").then((mod) => mod.Excalidraw), {
  ssr: false,
});

const SAVE_DEBOUNCE_MS = 2000;

export default function MLDepthWorkspace(props: WorkspaceProps) {
  const roundId = props.round.id;
  const [whiteboardOpen, setWhiteboardOpen] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [savedSummary, setSavedSummary] = useState<string>("");

  // Restores whatever scene was last autosaved (reconnect support), same
  // pattern as SystemDesignWorkspace.tsx - only relevant once the candidate
  // has opened the whiteboard at least once, since Excalidraw isn't mounted
  // (and initialData isn't called) until then.
  const initialData = useMemo(
    () => async () => {
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
    [roundId]
  );

  function handleChange(elements: readonly SceneElementLike[]) {
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

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-3">
      <AIInterviewerPanel {...props} />

      {!whiteboardOpen ? (
        <button
          type="button"
          onClick={() => setWhiteboardOpen(true)}
          className="self-start rounded-md border border-dashed border-border px-3 py-2 text-xs font-medium text-muted-foreground hover:border-border-strong hover:text-foreground"
        >
          + Open whiteboard (optional - for sketching a diagram)
        </button>
      ) : (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <p className="text-label font-semibold uppercase tracking-wide text-foreground">Whiteboard</p>
            <button
              type="button"
              onClick={() => setWhiteboardOpen(false)}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:border-border-strong"
            >
              Hide whiteboard
            </button>
          </div>
          {/* Excalidraw keeps its own light canvas intentionally (better diagram
              readability, specs/003-premium-uiux-redesign section 32) even in
              dark mode - only the frame around it follows the app's theme. */}
          <div className="h-[50vh] min-h-[360px] overflow-hidden rounded-lg border border-border bg-white">
            <Excalidraw
              initialData={initialData}
              onChange={(elements) => handleChange(elements as unknown as SceneElementLike[])}
            />
          </div>
        </div>
      )}
    </div>
  );
}
