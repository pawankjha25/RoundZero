"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import Link from "next/link";
import RoundTypeIcon, { type RoundTypeKey } from "@/components/RoundTypeIcon";
import { getOptions, me, startRound, type Options, type RoundModality, type User } from "@/lib/api";

// Only round types with a real interviewer can actually be started here -
// see apps/api/orchestrator.py's REAL_ROUND_TYPES (the backend re-validates
// this regardless; this is just what drives the label/icon on this page).
// ?type= query param picks which one; unset/unrecognized falls back to
// ml_system_design, this page's original and only round type before Coding
// got wired in.
const ROUND_TYPE_LABELS: Record<string, string> = {
  ml_system_design: "ML System Design",
  coding: "Coding",
  ml_depth: "ML Depth",
  backend_system_design: "Backend System Design",
  technical_leadership: "Technical Leadership",
  xfn: "Cross-functional",
};

// ML Depth's Domain field is repurposed as a sub-area picker (candidate
// request, 2026-09-03: "ML depth as Main area - and within that these
// subareas") - same domain mechanism ML System Design already uses to filter
// its own scenarios, just scoped down to the 3 sub-areas ml_depth's own
// scenarios.yaml actually tags (options.domains carries every round type's
// domains in one flat list, e.g. ml_infra/computer_vision, which don't apply
// here). The synthetic "" value below isn't a real DomainOption row - it's
// this page's own default, and MLDepthInterviewer.pick_scenario's existing
// progressive-relaxation fallback already treats an unmatched/empty domain
// as "any sub-area" with no backend change needed.
const ML_DEPTH_DOMAIN_VALUES = new Set(["llm_genai", "general_ml", "reinforcement_learning"]);
const ALL_SUBAREAS_OPTION = { value: "", label: "All sub-areas" };

export default function SetupPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roundType = ROUND_TYPE_LABELS[searchParams.get("type") ?? ""] ? (searchParams.get("type") as string) : "ml_system_design";
  const roundTypeLabel = ROUND_TYPE_LABELS[roundType];
  const isMLDepth = roundType === "ml_depth";
  const [user, setUser] = useState<User | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [roleFamily, setRoleFamily] = useState("");
  const [level, setLevel] = useState("");
  const [domain, setDomain] = useState("");
  const [company, setCompany] = useState("");
  const [duration, setDuration] = useState<number | null>(null);
  const [mode, setMode] = useState<RoundModality>("text");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => router.push("/login"));
    getOptions().then((opts) => {
      setOptions(opts);
      setRoleFamily(opts.role_families[0]?.value ?? "");
      setLevel(opts.levels[0]?.value ?? "");
      // ML Depth defaults to "All sub-areas" (the candidate's own call - see
      // ML_DEPTH_DOMAIN_VALUES above) rather than whichever domain happens to
      // sort first; every other round type keeps today's first-option default.
      setDomain(isMLDepth ? "" : opts.domains[0]?.value ?? "");
      setCompany(opts.companies[0]?.value ?? "");
      setDuration(opts.duration_minutes[0] ?? 45);
    });
  }, [router, isMLDepth]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!duration) return;
    setError(null);
    setLoading(true);
    try {
      const detail = await startRound({
        role_family: roleFamily,
        level,
        domain,
        company_profile: company,
        duration_minutes: duration,
        mode,
        round_type: roundType,
      });
      router.push(`/interview/${detail.round.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the interview");
      setLoading(false);
    }
  }

  if (!options) {
    return null;
  }

  return (
    <AppShell user={user} active="practice">
      <div className="mx-auto max-w-lg">
        <p className="mb-2 text-sm">
          <Link href="/practice" className="text-accent hover:underline">
            &larr; Practice
          </Link>
        </p>
        <h1 className="mb-1 text-xl font-semibold text-foreground">{roundTypeLabel}</h1>
        <p className="mb-8 text-base text-muted-foreground">Set up your target, then start.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Select label="Target role" value={roleFamily} onChange={setRoleFamily} options={options.role_families} />
          <Select
            label="Target Role Level"
            value={level}
            onChange={setLevel}
            options={options.levels}
            helperText="Select the level you are currently interviewing for."
          />
          {(level === "entry_level" || level === "mid_level" || level === "not_sure") && (
            <p className="-mt-2 text-xs text-muted-foreground">
              Heads up: every question and evaluation here is still calibrated for
              Senior/Staff/Principal - Entry Level and Mid-Level content and grading are on our
              roadmap, not live yet. You&apos;ll still get real feedback, just against a higher
              bar than your target level.
            </p>
          )}
          <Select
            label={isMLDepth ? "Sub-area" : "Domain"}
            value={domain}
            onChange={setDomain}
            options={
              isMLDepth
                ? [ALL_SUBAREAS_OPTION, ...options.domains.filter((d) => ML_DEPTH_DOMAIN_VALUES.has(d.value))]
                : options.domains
            }
          />
          <Select label="Company profile" value={company} onChange={setCompany} options={options.companies} />

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Duration</label>
            <select
              value={duration ?? ""}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            >
              {options.duration_minutes.map((d) => (
                <option key={d} value={d}>
                  {d} minutes
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Interview</label>
            <div className="flex items-center gap-2 rounded-md border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
              <RoundTypeIcon type={roundType as RoundTypeKey} />
              {roundTypeLabel}
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Format</label>
            <div className="grid grid-cols-3 gap-2">
              {(
                [
                  { value: "text", label: "Text" },
                  { value: "voice", label: "Voice" },
                  { value: "both", label: "Both" },
                ] as const
              ).map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setMode(opt.value)}
                  className={
                    "rounded-md border px-3 py-2 text-sm font-medium " +
                    (mode === opt.value
                      ? "border-accent bg-accent text-accent-foreground"
                      : "border-border bg-surface text-foreground hover:border-border-strong")
                  }
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {mode !== "text" && (
              <p className="mt-1.5 text-xs text-muted-foreground">
                Voice needs a microphone and a moment to connect once the round starts. If it
                can&apos;t connect, you can always continue by text.
              </p>
            )}
          </div>

          {error && <p className="text-sm text-status-strong-concern">{error}</p>}

          <Button type="submit" disabled={loading} fullWidth size="large">
            {loading ? "Starting..." : "Start interview"}
          </Button>
        </form>
      </div>
    </AppShell>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
  helperText,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  helperText?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-foreground">{label}</label>
      {helperText && <p className="mb-1 text-xs text-muted-foreground">{helperText}</p>}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
