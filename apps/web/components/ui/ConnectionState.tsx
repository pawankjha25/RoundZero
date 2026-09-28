// Design-system component. Errors must preserve candidate trust
// (specs/003-premium-uiux-redesign section 30) - during an interview, a
// connection problem should reassure ("your interview is saved") and offer
// Retry, never look like data was lost.
export default function ConnectionState({
  status,
  onRetry,
}: {
  status: "interrupted" | "reconnecting";
  onRetry?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-status-concern/30 bg-status-concern-bg px-4 py-2.5 text-sm">
      <div>
        <p className="font-medium text-status-concern">
          {status === "reconnecting" ? "Reconnecting..." : "Connection interrupted."}
        </p>
        <p className="text-status-concern/80">Your interview is saved.</p>
      </div>
      {onRetry && status === "interrupted" && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 rounded-md border border-status-concern/40 px-2.5 py-1 text-xs font-medium text-status-concern hover:bg-status-concern/10"
        >
          Retry Connection
        </button>
      )}
    </div>
  );
}
