"use client";

// Loop builder (specs/002-full-loop-platform P0.1) - create a loop with a
// name, one shared target-role config, and one or more planned rounds, all
// in one step (per the user's own call: "loop and interviews will create
// together"). Every round type is selectable; only the ones with a real
// interviewer today (ROUND_TYPES' `available` flag, mirrored server-side by
// apps/api/orchestrator.py::REAL_ROUND_TYPES) can actually be started later -
// the rest are included in the loop's shape honestly, same "show where it's
// headed" pattern the old /loop-planner preview used.
import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import RoundTypeIcon from "@/components/RoundTypeIcon";
import { ROUND_TYPES } from "@/lib/roundTypes";
import { createLoop, getOptions, me, suggestLoopName, type Options, type RoundModality, type User } from "@/lib/api";

export default function NewLoopPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [name, setName] = useState("");
  // Tracks whether the person has typed their own name (e.g. "Google-Staff
  // -MLE") - once true, changing role/level/company below never overwrites
  // it. Until then, the field auto-updates to match the current selection,
  // same pattern as a form field pre-filled from a computed default.
  const [nameEdited, setNameEdited] = useState(false);
  const [suggestedName, setSuggestedName] = useState("");
  const [roleFamily, setRoleFamily] = useState("");
  const [level, setLevel] = useState("");
  const [domain, setDomain] = useState("");
  const [company, setCompany] = useState("");
  const [mode, setMode] = useState<RoundModality>("text");
  const [selected, setSelected] = useState<Set<string>>(new Set(["ml_system_design"]));
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
      setDomain(opts.domains[0]?.value ?? "");
      setCompany(opts.companies[0]?.value ?? "");
    });
  }, [router]);

  // Re-suggest a name whenever role/level/company change - only applies it
  // to the field itself if the person hasn't typed their own name yet.
  useEffect(() => {
    if (!roleFamily || !level || !company) return;
    let cancelled = false;
    suggestLoopName({ role_family: roleFamily, level, company_profile: company })
      .then((res) => {
        if (cancelled) return;
        setSuggestedName(res.name);
        if (!nameEdited) setName(res.name);
      })
      .catch(() => {
        // Non-critical - the field just stays whatever it already was
        // (blank, or the last successful suggestion). Free text still works.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roleFamily, level, company]);

  function toggleRound(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (selected.size === 0) {
      setError("Pick at least one round for this loop.");
      return;
    }
    if (!name.trim()) {
      setError("Give this loop a name.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await createLoop({
        name: name.trim(),
        role_family: roleFamily,
        level,
        domain,
        company_profile: company,
        mode,
        rounds: ROUND_TYPES.filter((rt) => selected.has(rt.key)).map((rt) => ({
          round_type: rt.key,
          duration_minutes: rt.duration,
        })),
      });
      router.push("/loops");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create this loop");
      setLoading(false);
    }
  }

  if (!options) {
    return null;
  }

  return (
    <AppShell user={user} active="loops">
      <div className="mx-auto max-w-lg">
        <p className="mb-2 text-sm">
          <Link href="/loops" className="text-accent hover:underline">
            &larr; My Loops
          </Link>
        </p>
        <h1 className="mb-1 text-xl font-semibold text-foreground">Create a loop</h1>
        <p className="mb-8 text-base text-muted-foreground">
          A loop can hold one interview or several - pick everything you want in it now, start
          each one whenever you&apos;re ready.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="block text-sm font-medium text-foreground">Loop name</label>
              {nameEdited && suggestedName && suggestedName !== name && (
                <button
                  type="button"
                  onClick={() => {
                    setName(suggestedName);
                    setNameEdited(false);
                  }}
                  className="text-xs text-accent hover:underline"
                >
                  Use suggested name
                </button>
              )}
            </div>
            <input
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setNameEdited(true);
              }}
              placeholder="e.g. Acme Corp - Staff ML Engineer"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
            {!nameEdited && suggestedName && (
              <p className="mt-1 text-xs text-muted-foreground">Suggested - edit freely, it won&apos;t auto-update once you do.</p>
            )}
          </div>

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
          <Select label="Domain" value={domain} onChange={setDomain} options={options.domains} />
          <Select label="Company profile" value={company} onChange={setCompany} options={options.companies} />

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
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Interviews in this loop</label>
            <div className="space-y-2">
              {ROUND_TYPES.map((rt) => {
                const checked = selected.has(rt.key);
                return (
                  <label
                    key={rt.key}
                    className={
                      "flex cursor-pointer items-center justify-between rounded-md border p-3 " +
                      (checked ? "border-accent bg-accent/5" : "border-border hover:border-border-strong")
                    }
                  >
                    <span className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleRound(rt.key)}
                        className="h-4 w-4"
                      />
                      <RoundTypeIcon type={rt.key} className="text-foreground" />
                      <span className="text-sm font-medium text-foreground">{rt.label}</span>
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {rt.duration} min{!rt.available && " · not startable yet"}
                    </span>
                  </label>
                );
              })}
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">
              Six round types have real interviewers today (Hiring Manager is the one that
              doesn&apos;t yet) - you can add any of them to this loop, you just can&apos;t
              start Hiring Manager until it does.
            </p>
          </div>

          {error && <p className="text-sm text-status-strong-concern">{error}</p>}

          <Button type="submit" disabled={loading} fullWidth>
            {loading ? "Creating..." : "Create loop"}
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
