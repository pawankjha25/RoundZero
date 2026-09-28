"use client";

// Real interview detail (specs/002-full-loop-platform P0.11/P0.12) - the
// logged experience, a Log outcome form, and (only when the backend returns
// one - never fabricated client-side) a prediction-vs-actual comparison
// against a linked Round Zero loop.
import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import AIProcessState from "@/components/ui/AIProcessState";
import StatusBadge from "@/components/ui/StatusBadge";
import { formatLabel } from "@/lib/format";
import { hireSignalTone } from "@/lib/status";
import {
  deleteRealInterview,
  getRealInterview,
  me,
  upsertRealInterviewOutcome,
  type RealInterviewExperience,
  type User,
} from "@/lib/api";

const OUTCOME_LABELS: Record<string, string> = {
  rejected: "Rejected",
  advanced: "Advanced",
  offer: "Offer",
  withdrew: "Withdrew",
  no_response: "No response",
};

const OUTCOME_OPTIONS: { value: "rejected" | "advanced" | "offer" | "withdrew" | "no_response"; label: string }[] = [
  { value: "advanced", label: "Advanced" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrew", label: "Withdrew" },
  { value: "no_response", label: "No response" },
];

export default function RealInterviewDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [user, setUser] = useState<User | null>(null);
  const [experience, setExperience] = useState<RealInterviewExperience | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [status, setStatus] = useState<"rejected" | "advanced" | "offer" | "withdrew" | "no_response">("advanced");
  const [stage, setStage] = useState("");
  const [targetLevel, setTargetLevel] = useState("");
  const [offeredLevel, setOfferedLevel] = useState("");
  const [outcomeSaving, setOutcomeSaving] = useState(false);
  const [outcomeError, setOutcomeError] = useState<string | null>(null);
  const [showOutcomeForm, setShowOutcomeForm] = useState(false);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  useEffect(() => {
    if (!id) return;
    getRealInterview(id)
      .then((exp) => {
        setExperience(exp);
        if (exp.outcome) {
          setStatus(exp.outcome.status);
          setStage(exp.outcome.stage ?? "");
          setTargetLevel(exp.outcome.target_level ?? "");
          setOfferedLevel(exp.outcome.offered_level ?? "");
        } else {
          setTargetLevel(exp.level);
        }
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Could not load this interview"));
  }, [id]);

  async function handleOutcomeSubmit(e: FormEvent) {
    e.preventDefault();
    if (!experience) return;
    setOutcomeError(null);
    setOutcomeSaving(true);
    try {
      const updated = await upsertRealInterviewOutcome(experience.id, {
        status,
        stage: stage || null,
        target_level: targetLevel || null,
        offered_level: status === "offer" ? offeredLevel || null : null,
      });
      setExperience(updated);
      setShowOutcomeForm(false);
    } catch (err) {
      setOutcomeError(err instanceof Error ? err.message : "Could not save this outcome");
    } finally {
      setOutcomeSaving(false);
    }
  }

  async function handleDelete() {
    if (!experience) return;
    if (!window.confirm("Delete this logged interview? This can't be undone.")) return;
    await deleteRealInterview(experience.id);
    router.push("/real-interviews");
  }

  if (loadError) {
    return (
      <AppShell user={user} active="other">
        <div className="mx-auto max-w-2xl py-24 text-center">
          <p className="text-body text-muted-foreground">{loadError}</p>
        </div>
      </AppShell>
    );
  }

  if (!experience) {
    return (
      <AppShell user={user} active="other">
        <div className="mx-auto max-w-2xl py-24">
          <AIProcessState title="Loading" steps={[{ label: "Fetching interview", status: "active" }]} />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell user={user} active="other">
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <p className="mb-2 text-sm">
            <Link href="/real-interviews" className="text-accent hover:underline">
              &larr; Real interviews
            </Link>
          </p>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold text-foreground">
                {experience.company} - {formatLabel(experience.level)} {formatLabel(experience.role_family)}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {new Date(experience.interview_date).toLocaleDateString()}
                {experience.domain && ` - ${formatLabel(experience.domain)}`}
              </p>
            </div>
            <button onClick={handleDelete} className="shrink-0 text-xs text-muted-foreground hover:text-status-strong-concern">
              Delete
            </button>
          </div>
        </div>

        {/* Outcome section */}
        <div className="rounded-xl border border-border bg-surface p-5">
          {experience.outcome && !showOutcomeForm ? (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-label font-semibold uppercase tracking-wide text-foreground">Outcome</p>
                <p className="mt-1 text-body text-foreground">
                  {OUTCOME_LABELS[experience.outcome.status] ?? experience.outcome.status}
                  {experience.outcome.stage && ` - ${experience.outcome.stage}`}
                  {experience.outcome.offered_level && ` - offered ${formatLabel(experience.outcome.offered_level)}`}
                </p>
              </div>
              <button onClick={() => setShowOutcomeForm(true)} className="text-sm text-accent hover:underline">
                Update
              </button>
            </div>
          ) : (
            <form onSubmit={handleOutcomeSubmit} className="space-y-3">
              <p className="text-label font-semibold uppercase tracking-wide text-foreground">Log the outcome</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {OUTCOME_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setStatus(opt.value)}
                    className={
                      "rounded-md border px-3 py-2 text-sm font-medium " +
                      (status === opt.value
                        ? "border-accent bg-accent text-accent-foreground"
                        : "border-border bg-surface text-foreground hover:border-border-strong")
                    }
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <input
                type="text"
                value={stage}
                onChange={(e) => setStage(e.target.value)}
                placeholder="Stage (e.g. onsite, final round)"
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
              />
              {status === "offer" && (
                <input
                  type="text"
                  value={offeredLevel}
                  onChange={(e) => setOfferedLevel(e.target.value)}
                  placeholder="Level offered (optional - only if you want to note it)"
                  className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
                />
              )}
              {outcomeError && <p className="text-sm text-status-strong-concern">{outcomeError}</p>}
              <div className="flex items-center gap-2">
                <Button type="submit" disabled={outcomeSaving}>
                  {outcomeSaving ? "Saving..." : "Save outcome"}
                </Button>
                {experience.outcome && (
                  <button type="button" onClick={() => setShowOutcomeForm(false)} className="text-sm text-muted-foreground hover:text-foreground">
                    Cancel
                  </button>
                )}
              </div>
            </form>
          )}
        </div>

        {/* Prediction vs. outcome - only when the backend actually has both to compare. */}
        {experience.prediction && experience.outcome && (
          <div className="rounded-xl border border-border bg-surface p-5">
            <p className="mb-3 text-label font-semibold uppercase tracking-wide text-foreground">
              Round Zero prediction vs. real outcome
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">
                  Simulated ({experience.prediction.source === "committee" ? "committee verdict" : "round evaluation"})
                </p>
                <div className="mt-1 flex items-center gap-2">
                  <span className="text-lg font-semibold text-foreground">{experience.prediction.readiness_pct}%</span>
                  <StatusBadge label={experience.prediction.hire_signal} tone={hireSignalTone(experience.prediction.hire_signal)} />
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Real outcome</p>
                <div className="mt-1">
                  <span className="text-lg font-semibold text-foreground">
                    {OUTCOME_LABELS[experience.outcome.status] ?? experience.outcome.status}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
        {experience.linked_loop_attempt_id && !experience.prediction && (
          <p className="text-xs text-muted-foreground">
            Linked to a Round Zero loop, but nothing in it has been evaluated yet - no prediction to compare against.
          </p>
        )}

        {/* Rounds */}
        {experience.rounds.length > 0 && (
          <div>
            <h2 className="mb-3 text-lg font-semibold text-foreground">Rounds</h2>
            <div className="space-y-2">
              {experience.rounds.map((r, i) => (
                <div key={i} className="rounded-md border border-border p-3">
                  <p className="text-sm font-medium text-foreground">{r.round_type_label || "Round"}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{r.question_family}</p>
                  {r.follow_ups && <p className="mt-1 text-xs text-muted-foreground">Follow-ups: {r.follow_ups}</p>}
                  {r.difficulty && <p className="mt-1 text-xs text-muted-foreground">Difficulty: {r.difficulty}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {experience.self_assessment && (
          <div>
            <h2 className="mb-2 text-lg font-semibold text-foreground">Self-assessment</h2>
            <p className="text-body text-foreground">{experience.self_assessment}</p>
          </div>
        )}
      </div>
    </AppShell>
  );
}
