"use client";

import { useEffect, useRef, type RefObject } from "react";

// RZ-04 (UI/UX review, 2026-09-29): FeedbackWidget's sheet, EvidenceDrawer,
// and QuotaPill's popover each opened as mouse-only affordances - no
// Escape-to-close, no focus moved into the overlay on open, and no focus
// returned to whatever triggered it on close (so a keyboard/screen-reader
// user opening one had to tab in from wherever focus happened to already
// be, and closing it stranded focus on a now-invisible element). One
// shared hook instead of fixing this three slightly-different ways.
//
// - open: whether the overlay is currently shown.
// - onClose: called when Escape is pressed while open.
// - containerRef: the overlay's own root element, used to find its first
//   focusable descendant to focus on open.
//
// onClose is read through a ref rather than listed as an effect dependency
// so callers can pass an inline arrow function without re-subscribing the
// keydown listener (or restoring focus) on every render - only `open` and
// `containerRef` (stable across renders when created with useRef) actually
// need to re-run this effect.
export function useOverlayDismiss(
  open: boolean,
  onClose: () => void,
  containerRef: RefObject<HTMLElement | null>,
  // autoFocus: false for an overlay whose own open/close is driven by focus
  // itself (e.g. QuotaPill's popover, which closes on blur) - stealing
  // focus into the panel there would immediately blur its trigger and
  // race with that existing close-on-blur behavior. Defaults to true for
  // everything else (FeedbackWidget's sheet, EvidenceDrawer).
  { autoFocus = true }: { autoFocus?: boolean } = {}
) {
  const onCloseRef = useRef(onClose);
  // Keep the ref current without writing to it during render (the
  // react-hooks/refs rule flags a direct `ref.current = x` in the render
  // body) - this effect has no dependency array so it re-runs after every
  // render, same net effect with none of the render-phase write.
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;

    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    if (autoFocus) {
      const focusable = containerRef.current?.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      focusable?.focus();
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onCloseRef.current();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      trigger?.focus();
    };
  }, [open, containerRef, autoFocus]);
}
