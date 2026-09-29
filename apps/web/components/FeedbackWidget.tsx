"use client";

// Small-pilot "report an issue/feedback/advice" widget - mounted once,
// globally, in app/layout.tsx (a sibling of {children}, outside every
// page's own AppShell). Deliberately NOT a top-nav item - AppShell's own
// comment establishes that contextual surfaces stay out of top-level nav,
// and the interview room (app/interview/[roundId]/page.tsx) doesn't render
// AppShell at all, so a nav link would never reach a candidate mid-interview
// anyway. A floating button does: it's the one placement that's live on
// every route, active round included, which is exactly when a tester is
// most likely to have something to report.
//
// Hides itself on any route where `me()` fails (not logged in yet, e.g.
// /login) rather than redirecting - that's each page's own job, not this
// widget's.
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { me, submitFeedback, type FeedbackKind } from "@/lib/api";
import { useOverlayDismiss } from "@/lib/hooks/useOverlayDismiss";

const KIND_OPTIONS: { value: FeedbackKind; label: string }[] = [
  { value: "feedback", label: "Feedback" },
  { value: "issue", label: "Something's broken" },
  { value: "advice", label: "Advice for me" },
];

export default function FeedbackWidget() {
  const pathname = usePathname();
  const [signedIn, setSignedIn] = useState(false);
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<FeedbackKind>("feedback");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  useOverlayDismiss(open, () => setOpen(false), panelRef);

  useEffect(() => {
    me()
      .then(() => setSignedIn(true))
      .catch(() => setSignedIn(false));
  }, []);

  // Reset the "sent" confirmation and any stale error once the sheet is
  // reopened, so a second report starts from a clean form.
  function openSheet() {
    setOpen(true);
    setSent(false);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) {
      setError("Add a few words first.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await submitFeedback({ kind, message: trimmed, page_path: pathname });
      setSent(true);
      setMessage("");
    } catch {
      setError("Couldn't send that - try again in a moment.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!signedIn) {
    return null;
  }

  return (
    <>
      {open && (
        <div
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-40 bg-black/20"
          aria-hidden="true"
        />
      )}

      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label="Send feedback"
          className="fixed bottom-20 right-6 z-50 w-[min(22rem,calc(100vw-3rem))] rounded-lg border border-border bg-surface p-4 shadow-xl"
        >
          {sent ? (
            <div className="py-2 text-center">
              <p className="text-sm font-medium text-foreground">Thanks - got it.</p>
              <p className="mt-1 text-xs text-muted-foreground">Pawan reads every one of these during the pilot.</p>
              <button
                onClick={() => setOpen(false)}
                className="mt-3 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:border-border-strong"
              >
                Close
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">Report feedback, an issue, or advice</p>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Close"
                  className="text-muted-foreground hover:text-foreground"
                >
                  ✕
                </button>
              </div>

              <div className="mt-3 flex gap-1.5">
                {KIND_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setKind(opt.value)}
                    className={
                      "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors " +
                      (kind === opt.value
                        ? "border-accent bg-accent text-accent-foreground"
                        : "border-border text-muted-foreground hover:border-border-strong")
                    }
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="What's on your mind?"
                rows={4}
                className="mt-3 w-full resize-none rounded-md border border-border bg-background p-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent"
              />

              {error && <p className="mt-1.5 text-xs text-status-strong-concern">{error}</p>}

              <button
                type="submit"
                disabled={submitting}
                className="mt-3 w-full rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {submitting ? "Sending..." : "Send"}
              </button>
            </form>
          )}
        </div>
      )}

      <button
        onClick={() => (open ? setOpen(false) : openSheet())}
        aria-label="Send feedback"
        className="fixed bottom-6 right-6 z-50 rounded-full border border-border bg-surface px-4 py-2.5 text-sm font-medium text-foreground shadow-lg hover:border-border-strong"
      >
        Feedback
      </button>
    </>
  );
}
