// Small inline-SVG icon per round type (configs/loops/principal_ml_infra.yaml).
// Hand-authored line icons rather than an external icon font/library, so there's
// no extra dependency and everything themes with currentColor.
export type RoundTypeKey =
  | "coding"
  | "ml_system_design"
  | "backend_system_design"
  | "ml_depth"
  | "technical_leadership"
  | "xfn"
  | "hiring_manager";

const PATHS: Record<RoundTypeKey, React.ReactNode> = {
  coding: (
    <path
      d="M8 6 3 12l5 6M16 6l5 6-5 6"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
  ),
  ml_system_design: (
    <g stroke="currentColor" strokeWidth="1.75" fill="none">
      <circle cx="6" cy="7" r="2.25" />
      <circle cx="18" cy="7" r="2.25" />
      <circle cx="12" cy="18" r="2.25" />
      <path d="M8 8.3 10.3 15.7M16 8.3 13.7 15.7" strokeLinecap="round" />
    </g>
  ),
  backend_system_design: (
    <g stroke="currentColor" strokeWidth="1.75" fill="none" strokeLinecap="round">
      <rect x="4" y="4" width="16" height="5" rx="1.25" />
      <rect x="4" y="10.5" width="16" height="5" rx="1.25" />
      <rect x="4" y="17" width="16" height="3" rx="1" />
    </g>
  ),
  ml_depth: (
    <g stroke="currentColor" strokeWidth="1.75" fill="none" strokeLinejoin="round">
      <path d="M12 3 20 7.5v9L12 21 4 16.5v-9Z" />
      <circle cx="12" cy="12" r="2.25" fill="currentColor" stroke="none" />
    </g>
  ),
  technical_leadership: (
    <g stroke="currentColor" strokeWidth="1.75" fill="none">
      <circle cx="12" cy="12" r="8.5" />
      <path d="m15 9-4.2 2.8L9 16l4.2-2.8Z" strokeLinejoin="round" />
    </g>
  ),
  xfn: (
    <g stroke="currentColor" strokeWidth="1.75" fill="none">
      <circle cx="9.5" cy="12" r="6" />
      <circle cx="14.5" cy="12" r="6" />
    </g>
  ),
  hiring_manager: (
    <g stroke="currentColor" strokeWidth="1.75" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3.5" y="8" width="17" height="11" rx="1.5" />
      <path d="M8.5 8V6a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v2" />
    </g>
  ),
};

export default function RoundTypeIcon({ type, className = "" }: { type: RoundTypeKey; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" className={className} aria-hidden="true">
      {PATHS[type]}
    </svg>
  );
}
