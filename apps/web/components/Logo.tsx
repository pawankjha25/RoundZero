// Inline SVG wordmark - no external image assets/hosting needed. The mark is a
// simple ring ("Round") - deliberately plain so it scales crisply at any size
// and themes with currentColor instead of needing light/dark image variants.
export default function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={"inline-flex items-center gap-2 " + className}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" />
        <circle cx="12" cy="12" r="2" fill="currentColor" />
      </svg>
      <span className="text-sm font-semibold tracking-tight">Round Zero</span>
    </span>
  );
}
