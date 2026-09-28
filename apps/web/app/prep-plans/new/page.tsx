"use client";

// Create a Prep Plan (user-pitched feature) - one target role/level/domain/
// company/duration/mode, set once here, so every question added later
// inherits it - starting a question is never a second form (see
// orchestrator.start_round_from_plan_question's docstring).
import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import { createPrepPlan, getOptions, me, type Options, type RoundModality, type User } from "@/lib/api";

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

export default function NewPrepPlanPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [options, setOptions] = useState<Options | null>(null);

  const [name, setName] = useState("");
  const [roleFamily, setRoleFamily] = useState("");
  const [level, setLevel] = useState("");
  const [domain, setDomain] = useState("");
  const [company, setCompany] = useState("");
  const [duration, setDuration] = useState(45);
  const [mode, setMode] = useState<RoundModality>("text");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      setDuration(opts.duration_minutes[0] ?? 45);
    });
  }, [router]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Give this plan a name.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const plan = await createPrepPlan({
        name: name.trim(),
        role_family: roleFamily,
        level,
        domain,
        company_profile: company,
        duration_minutes: duration,
        mode,
      });
      router.push(`/prep-plans/${plan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create this plan");
      setSaving(false);
    }
  }

  if (!options) {
    return null;
  }

  return (
    <AppShell user={user} active="practice">
      <div className="mx-auto max-w-lg">
        <p className="mb-2 text-sm">
          <Link href="/prep-plans" className="text-accent hover:underline">
            &larr; Prep plans
          </Link>
        </p>
        <h1 className="mb-1 text-xl font-semibold text-foreground">Create a plan</h1>
        <p className="mb-8 text-base text-muted-foreground">
          Set your target once - every question you add to this plan runs against it, so picking a
          question to practice is always just one click.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Plan name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Staff MLE prep"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
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
            <label className="mb-1 block text-sm font-medium text-foreground">Default round length</label>
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            >
              {options.duration_minutes.map((d) => (
                <option key={d} value={d}>
                  {d} min
                </option>
              ))}
            </select>
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
          </div>

          {error && <p className="text-sm text-status-strong-concern">{error}</p>}

          <Button type="submit" disabled={saving} fullWidth>
            {saving ? "Creating..." : "Create plan"}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Next you&apos;ll add areas (e.g. System Design, Coding) and the specific questions to drill in each.
          </p>
        </form>
      </div>
    </AppShell>
  );
}
