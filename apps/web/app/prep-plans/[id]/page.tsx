"use client";

// Prep Plan detail (user-pitched feature, not from the P0 backlog) - the
// main view: areas tagged to a real round type, each holding a list of
// questions the candidate picks from deliberately. Clicking a question
// starts a round against exactly that scenario (orchestrator.
// start_round_from_plan_question) and routes straight into the normal
// interview room, same as /setup's "Start Interview" - see
// startRoundFromQuestion's docstring in lib/api.ts.
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import RoundTypeIcon, { type RoundTypeKey } from "@/components/RoundTypeIcon";
import { ROUND_TYPES } from "@/lib/roundTypes";
import { formatLabel } from "@/lib/format";
import {
  addCustomQuestion,
  addPrepPlanArea,
  addQuestionFromBank,
  addSuggestedQuestion,
  deletePrepPlan,
  deletePrepPlanArea,
  deletePrepPlanQuestion,
  getPrepPlan,
  listBankScenarios,
  me,
  startRoundFromQuestion,
  suggestQuestions,
  type BankScenario,
  type PrepPlan,
  type PrepPlanArea,
  type PrepPlanQuestion,
  type SuggestedQuestion,
  type User,
} from "@/lib/api";

const AVAILABLE_ROUND_TYPES = ROUND_TYPES.filter((rt) => rt.available);
const FREEFORM_ROUND_TYPES = new Set([
  "ml_system_design",
  "ml_depth",
  "backend_system_design",
  "technical_leadership",
  "xfn",
]);

const SOURCE_LABELS: Record<string, string> = { bank: "From bank", custom: "Your own", ai: "AI suggested" };

function progressLabel(q: PrepPlanQuestion): string {
  if (q.progress.attempts === 0) return "Not tried yet";
  const parts = [`Tried ${q.progress.attempts}x`];
  if (q.progress.latest_readiness_pct !== null) parts.push(`last ${q.progress.latest_readiness_pct}% ${q.progress.latest_hire_signal ?? ""}`.trim());
  return parts.join(" - ");
}

function QuestionRow({
  question,
  starting,
  onStart,
  onDelete,
}: {
  question: PrepPlanQuestion;
  starting: boolean;
  onStart: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-md border border-border p-3">
      <button
        type="button"
        onClick={onStart}
        disabled={starting}
        className="flex-1 text-left disabled:opacity-50"
      >
        <p className="text-sm font-medium text-foreground">{question.prompt}</p>
        {question.notes && <p className="mt-0.5 text-xs text-muted-foreground">{question.notes}</p>}
        <p className="mt-1 text-xs text-muted-foreground">
          {SOURCE_LABELS[question.source] ?? question.source} - {progressLabel(question)}
        </p>
      </button>
      <div className="flex shrink-0 flex-col items-end gap-1">
        <button
          type="button"
          onClick={onStart}
          disabled={starting}
          className="text-xs font-medium text-accent hover:underline disabled:opacity-50"
        >
          {starting ? "Starting..." : "Start →"}
        </button>
        <button type="button" onClick={onDelete} className="text-xs font-medium text-status-strong-concern hover:underline">
          Remove
        </button>
      </div>
    </div>
  );
}

function AreaCard({
  area,
  plan,
  onReload,
  onStart,
  startingId,
}: {
  area: PrepPlanArea;
  plan: PrepPlan;
  onReload: () => void;
  onStart: (questionId: string) => void;
  startingId: string | null;
}) {
  const [error, setError] = useState<string | null>(null);

  const [bankOpen, setBankOpen] = useState(false);
  const [bank, setBank] = useState<BankScenario[] | null>(null);
  const [bankLoading, setBankLoading] = useState(false);

  const [customOpen, setCustomOpen] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");
  const [customNotes, setCustomNotes] = useState("");
  const [customSaving, setCustomSaving] = useState(false);

  const [suggestions, setSuggestions] = useState<SuggestedQuestion[] | null>(null);
  const [suggesting, setSuggesting] = useState(false);

  const allowsFreeform = FREEFORM_ROUND_TYPES.has(area.round_type);

  async function toggleBank() {
    if (bankOpen) {
      setBankOpen(false);
      return;
    }
    setBankOpen(true);
    setBankLoading(true);
    setError(null);
    try {
      setBank(await listBankScenarios(area.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the scenario bank");
    } finally {
      setBankLoading(false);
    }
  }

  async function handleAddFromBank(scenarioId: string) {
    setError(null);
    try {
      await addQuestionFromBank(area.id, scenarioId);
      setBank((prev) => (prev ? prev.filter((s) => s.scenario_id !== scenarioId) : prev));
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this question");
    }
  }

  async function handleAddCustom() {
    if (!customPrompt.trim()) return;
    setError(null);
    setCustomSaving(true);
    try {
      await addCustomQuestion(area.id, customPrompt.trim(), customNotes.trim());
      setCustomPrompt("");
      setCustomNotes("");
      setCustomOpen(false);
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this question");
    } finally {
      setCustomSaving(false);
    }
  }

  async function handleSuggest() {
    setError(null);
    setSuggesting(true);
    try {
      setSuggestions(await suggestQuestions(area.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not get suggestions right now");
    } finally {
      setSuggesting(false);
    }
  }

  async function handleAddSuggestion(s: SuggestedQuestion) {
    setError(null);
    try {
      await addSuggestedQuestion(area.id, s);
      setSuggestions((prev) => (prev ? prev.filter((x) => x !== s) : prev));
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this question");
    }
  }

  async function handleDeleteQuestion(questionId: string) {
    setError(null);
    try {
      await deletePrepPlanQuestion(questionId);
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove this question");
    }
  }

  async function handleDeleteArea() {
    if (!window.confirm(`Remove the "${area.label}" area and all its questions?`)) return;
    setError(null);
    try {
      await deletePrepPlanArea(area.id);
      onReload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove this area");
    }
  }

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <RoundTypeIcon type={area.round_type as RoundTypeKey} className="text-foreground" />
          <div>
            <p className="text-sm font-semibold text-foreground">{area.label}</p>
            <p className="text-xs text-muted-foreground">{formatLabel(area.round_type)}</p>
          </div>
        </div>
        <button type="button" onClick={handleDeleteArea} className="text-xs font-medium text-status-strong-concern hover:underline">
          Delete area
        </button>
      </div>

      {area.questions.length > 0 && (
        <div className="mb-3 space-y-2">
          {area.questions.map((q) => (
            <QuestionRow
              key={q.id}
              question={q}
              starting={startingId === q.id}
              onStart={() => onStart(q.id)}
              onDelete={() => handleDeleteQuestion(q.id)}
            />
          ))}
        </div>
      )}

      {error && <p className="mb-2 text-sm text-status-strong-concern">{error}</p>}

      <div className="flex flex-wrap gap-3 text-sm">
        <button type="button" onClick={toggleBank} className="text-accent hover:underline">
          + Add from bank
        </button>
        {allowsFreeform && (
          <button type="button" onClick={() => setCustomOpen((v) => !v)} className="text-accent hover:underline">
            + Write your own
          </button>
        )}
        <button type="button" onClick={handleSuggest} disabled={suggesting} className="text-accent hover:underline disabled:opacity-50">
          {suggesting ? "Suggesting..." : "✨ Suggest questions"}
        </button>
      </div>

      {bankOpen && (
        <div className="mt-3 space-y-2 rounded-md border border-border bg-surface p-3">
          {bankLoading ? (
            <p className="text-xs text-muted-foreground">Loading...</p>
          ) : bank && bank.length > 0 ? (
            bank.map((s) => (
              <div key={s.scenario_id} className="flex items-start justify-between gap-3">
                <p className="text-sm text-foreground">{s.title ? `${s.title} - ` : ""}{s.prompt}</p>
                <button type="button" onClick={() => handleAddFromBank(s.scenario_id)} className="shrink-0 text-xs font-medium text-accent hover:underline">
                  Add
                </button>
              </div>
            ))
          ) : (
            <p className="text-xs text-muted-foreground">Nothing left in the bank for {plan.level}/{plan.domain} that isn&apos;t already in this area.</p>
          )}
        </div>
      )}

      {customOpen && (
        <div className="mt-3 space-y-2 rounded-md border border-border bg-surface p-3">
          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            rows={2}
            placeholder="The question itself"
            className="w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-foreground focus:border-accent focus:outline-none"
          />
          <input
            type="text"
            value={customNotes}
            onChange={(e) => setCustomNotes(e.target.value)}
            placeholder="Notes (optional)"
            className="w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-foreground focus:border-accent focus:outline-none"
          />
          <button
            type="button"
            onClick={handleAddCustom}
            disabled={!customPrompt.trim() || customSaving}
            className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-foreground hover:border-border-strong disabled:opacity-50"
          >
            {customSaving ? "Adding..." : "Add question"}
          </button>
        </div>
      )}

      {suggestions && (
        <div className="mt-3 space-y-2 rounded-md border border-border bg-surface p-3">
          {suggestions.length === 0 ? (
            <p className="text-xs text-muted-foreground">No new suggestions right now.</p>
          ) : (
            suggestions.map((s, i) => (
              <div key={i} className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm text-foreground">{s.prompt}</p>
                  {s.notes && <p className="text-xs text-muted-foreground">{s.notes}</p>}
                </div>
                <button type="button" onClick={() => handleAddSuggestion(s)} className="shrink-0 text-xs font-medium text-accent hover:underline">
                  Add
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default function PrepPlanDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const planId = params.id;

  const [user, setUser] = useState<User | null>(null);
  const [plan, setPlan] = useState<PrepPlan | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [startingId, setStartingId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  const [addAreaOpen, setAddAreaOpen] = useState(false);
  const [newAreaRoundType, setNewAreaRoundType] = useState<string>(AVAILABLE_ROUND_TYPES[0]?.key ?? "ml_system_design");
  const [newAreaLabel, setNewAreaLabel] = useState("");
  const [addingArea, setAddingArea] = useState(false);

  function reload() {
    getPrepPlan(planId)
      .then(setPlan)
      .catch(() => setLoadError("Could not load this plan"));
  }

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => router.push("/login"));
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planId, router]);

  async function handleStart(questionId: string) {
    setStartError(null);
    setStartingId(questionId);
    try {
      const detail = await startRoundFromQuestion(questionId);
      router.push(`/interview/${detail.round.id}`);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Could not start this round");
      setStartingId(null);
    }
  }

  async function handleAddArea() {
    if (!newAreaLabel.trim()) return;
    setAddingArea(true);
    try {
      await addPrepPlanArea(planId, newAreaRoundType, newAreaLabel.trim());
      setNewAreaLabel("");
      setAddAreaOpen(false);
      reload();
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Could not add this area");
    } finally {
      setAddingArea(false);
    }
  }

  async function handleDeletePlan() {
    if (!plan || !window.confirm(`Delete "${plan.name}" and everything in it?`)) return;
    try {
      await deletePrepPlan(plan.id);
      router.push("/prep-plans");
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Could not delete this plan");
    }
  }

  if (loadError) {
    return (
      <AppShell user={user} active="practice">
        <p className="text-sm text-status-strong-concern">{loadError}</p>
      </AppShell>
    );
  }
  if (!plan) {
    return null;
  }

  return (
    <AppShell user={user} active="practice">
      <div className="mx-auto max-w-2xl space-y-6">
        <p className="text-sm">
          <Link href="/prep-plans" className="text-accent hover:underline">
            &larr; Prep plans
          </Link>
        </p>

        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-foreground">{plan.name}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Targeting {formatLabel(plan.level)} {formatLabel(plan.role_family)} - {formatLabel(plan.domain)} - every
              question here runs against this target, {plan.duration_minutes} min, {plan.mode}.
            </p>
          </div>
          <button type="button" onClick={handleDeletePlan} className="shrink-0 text-sm font-medium text-status-strong-concern hover:underline">
            Delete
          </button>
        </div>

        {startError && <p className="text-sm text-status-strong-concern">{startError}</p>}

        <div className="space-y-4">
          {plan.areas.map((area) => (
            <AreaCard key={area.id} area={area} plan={plan} onReload={reload} onStart={handleStart} startingId={startingId} />
          ))}
        </div>

        <div className="rounded-lg border border-dashed border-border p-4">
          {addAreaOpen ? (
            <div className="space-y-2">
              <select
                value={newAreaRoundType}
                onChange={(e) => setNewAreaRoundType(e.target.value)}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
              >
                {AVAILABLE_ROUND_TYPES.map((rt) => (
                  <option key={rt.key} value={rt.key}>
                    {rt.label}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={newAreaLabel}
                onChange={(e) => setNewAreaLabel(e.target.value)}
                placeholder="Area name, e.g. Feature stores"
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleAddArea}
                  disabled={!newAreaLabel.trim() || addingArea}
                  className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-foreground hover:opacity-90 disabled:opacity-50"
                >
                  {addingArea ? "Adding..." : "Add area"}
                </button>
                <button
                  type="button"
                  onClick={() => setAddAreaOpen(false)}
                  className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-foreground hover:border-border-strong"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button type="button" onClick={() => setAddAreaOpen(true)} className="text-sm font-medium text-accent hover:underline">
              + Add area
            </button>
          )}
        </div>
      </div>
    </AppShell>
  );
}
