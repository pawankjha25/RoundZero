import { toneClasses, type StatusTone } from "@/lib/status";

// Design-system component (specs/003-premium-uiux-redesign section 36's
// component list). A single consistent pill for any status/signal in the
// app - hire signal, connection state, round status. Always renders a text
// label alongside color (never color-only), per the spec's accessibility
// rule.
export default function StatusBadge({
  label,
  tone,
  className = "",
}: {
  label: string;
  tone: StatusTone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${toneClasses(tone)} ${className}`}
    >
      {label}
    </span>
  );
}
