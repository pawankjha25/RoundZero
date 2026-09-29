"use client";

// Log a real interview (specs/002-full-loop-platform P0.11) - typed fields
// plus an optional freeform dump the candidate can have AI break into a
// per-round draft (never auto-saved - see structureRealInterviewText's own
// docstring: this is a preview call only, Save is the only thing that
// persists anything). Reachable from the dashboard, a finished loop's card
// (which pre-fills role/level/domain/loop via query params - never company,
// which is always typed fresh), or /intel.
import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import {
  createRealInterview,
  defaultLevel,
  getOptions,
  listLoops,
  me,
  structureRealInterviewText,
  type Loop,
  type Options,
  type RealInterviewRound,
  type User,
} from "@/lib/api";

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-foreground">{label}</label>
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

const VISIBILITY_OPTIONS: { value: "private" | "anonymous" | "community"; label: string; description: string }[] = [
  { value: "private", label: "Private", description: "Only you can ever see this entry." },
  {
    value: "anonymous",
    label: "Anonymous",
    description: "Could help other candidates researching this company later, with nothing that identifies you attached. Not shared anywhere yet.",
  },
  {
    value: "community",
    label: "Community",
    description: "Could be shown to other candidates researching this company, credited to you. Not shared anywhere yet.",
  },
];

function NewRealInterviewPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [user, setUser] = useState<User | null>(null);
  const [options, setOptions] = useState<Options | null>(null);
  const [loops, setLoops] = useState<Loop[]>([]);

  const [company, setCompany] = useState("");
  const [roleFamily, setRoleFamily] = useState("");
  const [level, setLevel] = useState("");
  const [domain, setDomain] = useState("");
  const [interviewDate, setInterviewDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [linkedLoopId, setLinkedLoopId] = useState<string>(() => searchParams.get("loop_id") ?? "");

  const [rawText, setRawText] = useState("");
  const [structuring, setStructuring] = useState(false);
  const [structureError, setStructureError] = useState<string | null>(null);
  const [rounds, setRounds] = useState<RealInterviewRound[]>([]);
  const [selfAssessment, setSelfAssessment] = useState("");
  const [visibility, setVisibility] = useState<"private" | "anonymous" | "community">("private");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => router.push("/login"));
    getOptions().then((opts) => {
      setOptions(opts);
      setRoleFamily(searchParams.get("role_family") ?? opts.role_families[0]?.value ?? "");
      setLevel(searchParams.get("level") ?? defaultLevel(opts.levels));
      setDomain(searchParams.get("domain") ?? opts.domains[0]?.value ?? "");
    });
    listLoops().then(setLoops).catch(() => setLoops([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  function updateRound(index: number, patch: Partial<RealInterviewRound>) {
    setRounds((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  function removeRound(index: number) {
    setRounds((prev) => prev.filter((_, i) => i !== index));
  }

  function addBlankRound() {
    setRounds((prev) => [...prev, { round_type_label: "", question_family: "", follow_ups: "", difficulty: "" }]);
  }

  async function handleStructure() {
    if (!rawText.trim()) return;
    setStructureError(null);
    setStructuring(true);
    try {
      const hints = `${level} ${roleFamily}, ${domain} domain${company ? `, at ${company}` : ""}`;
      const structured = await structureRealInterviewText(rawText, hints);
      setRounds(structured.rounds);
      if (structured.self_assessment) setSelfAssessment(structured.self_assessment);
    } catch (err) {
      setStructureError(err instanceof Error ? err.message : "Could not structure this - you can still fill in rounds manually below.");
    } finally {
      setStructuring(false);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!company.trim()) {
      setSaveError("Which company was this interview at?");
      return;
    }
    setSaveError(null);
    setSaving(true);
    try {
      const experience = await createRealInterview({
        company: company.trim(),
        role_family: roleFamily,
        level,
        domain: domain || null,
        interview_date: new Date(interviewDate).toISOString(),
        linked_loop_attempt_id: linkedLoopId || null,
        rounds,
        notes: rawText || null,
        self_assessment: selfAssessment || null,
        visibility,
      });
      router.push(`/real-interviews/${experience.id}`);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Could not save this interview");
      setSaving(false);
    }
  }

  if (!options) {
    return null;
  }

  return (
    <AppShell user={user} active="other">
      <div className="mx-auto max-w-lg">
        <p className="mb-2 text-sm">
          <Link href="/real-interviews" className="text-accent hover:underline">
            &larr; Real interviews
          </Link>
        </p>
        <h1 className="mb-1 text-xl font-semibold text-foreground">Log a real interview</h1>
        <p className="mb-8 text-base text-muted-foreground">
          Focus on question types and topics - please don&apos;t include interviewer names, confidential
          specifics, or anything you signed an NDA about.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Company</label>
            <input
              type="text"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="e.g. Anthropic"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
          </div>

          <Select label="Role" value={roleFamily} onChange={setRoleFamily} options={options.role_families} />
          <Select label="Level" value={level} onChange={setLevel} options={options.levels} />
          <Select label="Domain" value={domain} onChange={setDomain} options={options.domains} />

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Interview date</label>
            <input
              type="date"
              value={interviewDate}
              onChange={(e) => setInterviewDate(e.target.value)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
          </div>

          {loops.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">
                Related Round Zero loop <span className="font-normal text-muted-foreground">(optional)</span>
              </label>
              <select
                value={linkedLoopId}
                onChange={(e) => setLinkedLoopId(e.target.value)}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
              >
                <option value="">Not linked to a practice loop</option>
                {loops.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-muted-foreground">
                Link the loop you practiced with for this company, and we&apos;ll show your simulated readiness next to
                how it actually went.
              </p>
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">What happened</label>
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              rows={5}
              placeholder="Write freely about the rounds, question topics, and how it felt - no interviewer names or confidential specifics."
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
            <div className="mt-2 flex items-center gap-3">
              <button
                type="button"
                onClick={handleStructure}
                disabled={!rawText.trim() || structuring}
                className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-foreground hover:border-border-strong disabled:opacity-50"
              >
                {structuring ? "Structuring..." : "Structure with AI"}
              </button>
              <span className="text-xs text-muted-foreground">Drafts an editable per-round breakdown below - nothing saves until you hit Save.</span>
            </div>
            {structureError && <p className="mt-2 text-sm text-status-strong-concern">{structureError}</p>}
          </div>

          {rounds.length > 0 && (
            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">Rounds</label>
              <div className="space-y-3">
                {rounds.map((r, i) => (
                  <div key={i} className="rounded-md border border-border p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <input
                        type="text"
                        value={r.round_type_label}
                        onChange={(e) => updateRound(i, { round_type_label: e.target.value })}
                        placeholder="Round type (e.g. System Design)"
                        className="w-full rounded-md border border-border bg-surface px-2 py-1 text-sm font-medium text-foreground focus:border-accent focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => removeRound(i)}
                        className="ml-2 shrink-0 text-xs text-muted-foreground hover:text-foreground"
                      >
                        Remove
                      </button>
                    </div>
                    <textarea
                      value={r.question_family}
                      onChange={(e) => updateRound(i, { question_family: e.target.value })}
                      placeholder="Question topic/family"
                      rows={2}
                      className="mb-2 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-foreground focus:border-accent focus:outline-none"
                    />
                    <input
                      type="text"
                      value={r.follow_ups}
                      onChange={(e) => updateRound(i, { follow_ups: e.target.value })}
                      placeholder="Follow-ups (optional)"
                      className="mb-2 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-foreground focus:border-accent focus:outline-none"
                    />
                    <input
                      type="text"
                      value={r.difficulty}
                      onChange={(e) => updateRound(i, { difficulty: e.target.value })}
                      placeholder="Difficulty, in your own words (optional)"
                      className="w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-foreground focus:border-accent focus:outline-none"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
          <button
            type="button"
            onClick={addBlankRound}
            className="text-sm text-accent hover:underline"
          >
            + Add a round manually
          </button>

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">
              Self-assessment <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <textarea
              value={selfAssessment}
              onChange={(e) => setSelfAssessment(e.target.value)}
              rows={2}
              placeholder="How do you think it went?"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium text-foreground">Who can see this</label>
            <div className="space-y-2">
              {VISIBILITY_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className={
                    "flex cursor-pointer items-start gap-3 rounded-md border p-3 " +
                    (visibility === opt.value ? "border-accent bg-accent/5" : "border-border hover:border-border-strong")
                  }
                >
                  <input
                    type="radio"
                    name="visibility"
                    checked={visibility === opt.value}
                    onChange={() => setVisibility(opt.value)}
                    className="mt-0.5 h-4 w-4"
                  />
                  <span>
                    <span className="block text-sm font-medium text-foreground">{opt.label}</span>
                    <span className="block text-xs text-muted-foreground">{opt.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          {saveError && <p className="text-sm text-status-strong-concern">{saveError}</p>}

          <Button type="submit" disabled={saving} fullWidth>
            {saving ? "Saving..." : "Save"}
          </Button>
        </form>
      </div>
    </AppShell>
  );
}

export default function NewRealInterviewPage() {
  return (
    <Suspense fallback={null}>
      <NewRealInterviewPageContent />
    </Suspense>
  );
}
