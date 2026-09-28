"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import { COMPANY_TIERS } from "@/lib/companyTiers";
import {
  me,
  adminListOptions,
  adminCreateOption,
  adminUpdateOption,
  adminDeleteOption,
  adminListDurations,
  adminCreateDuration,
  adminDeleteDuration,
  adminListRoundTypes,
  adminUpdateRoundType,
  adminListStudyResources,
  adminCreateStudyResource,
  adminUpdateStudyResource,
  adminDeleteStudyResource,
  adminListSettings,
  adminUpdateSetting,
  adminListFeedback,
  type AdminOptionKind,
  type AdminOptionRow,
  type AdminDuration,
  type AdminRoundType,
  type AdminStudyResource,
  type AdminFeedback,
  type User,
} from "@/lib/api";

// Suggestions only (a <datalist>, not a locked enum) - kept here for admin
// convenience so study resources are easy to tag correctly, but deliberately
// NOT enforced client-side, since the source of truth for dimension keys is
// rubrics/ml_system_design/v1.yaml (CLAUDE.md decision 2 - rubrics are
// config, not code baked into the UI). If the rubric ever adds a dimension,
// this list just stops suggesting it - nothing breaks.
const DIMENSION_SUGGESTIONS = [
  { key: "framing", label: "Problem framing / requirements" },
  { key: "architecture", label: "High-level architecture" },
  { key: "modeling", label: "ML / model reasoning" },
  { key: "data_training", label: "Data / training" },
  { key: "serving_scalability", label: "Serving / scalability" },
  { key: "reliability", label: "Reliability" },
  { key: "evaluation_monitoring", label: "Evaluation / monitoring" },
  { key: "cost_efficiency", label: "Cost / efficiency" },
  { key: "trade_offs", label: "Trade-off reasoning" },
  { key: "communication", label: "Communication" },
];

const OPTION_SECTIONS: { kind: AdminOptionKind; title: string }[] = [
  { kind: "role-families", title: "Role families" },
  { kind: "levels", title: "Levels" },
  { kind: "domains", title: "Domains" },
  { kind: "companies", title: "Companies" },
];

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h2 className="mb-3 text-sm font-semibold text-foreground">{title}</h2>
      {children}
    </div>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={
        "rounded-md border border-border bg-surface px-2 py-1 text-sm text-foreground " +
        (props.className ?? "")
      }
    />
  );
}

function SmallButton({
  children,
  onClick,
  variant = "default",
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  variant?: "default" | "danger";
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={
        "rounded-md border px-2 py-1 text-xs font-medium disabled:opacity-50 " +
        (variant === "danger"
          ? "border-status-strong-concern/40 text-status-strong-concern hover:bg-status-strong-concern-bg"
          : "border-border text-foreground hover:border-border-strong")
      }
    >
      {children}
    </button>
  );
}

function OptionListEditor({ kind, title }: { kind: AdminOptionKind; title: string }) {
  const [rows, setRows] = useState<AdminOptionRow[] | null>(null);
  const [newValue, setNewValue] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reload() {
    adminListOptions(kind)
      .then(setRows)
      .catch(() => setError("Failed to load."));
  }

  useEffect(reload, [kind]);

  async function handleAdd() {
    if (!newValue.trim() || !newLabel.trim()) return;
    setError(null);
    try {
      await adminCreateOption(kind, { value: newValue.trim(), label: newLabel.trim(), sort_order: rows?.length ?? 0 });
      setNewValue("");
      setNewLabel("");
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add.");
    }
  }

  async function handleLabelChange(value: string, label: string) {
    try {
      await adminUpdateOption(kind, value, { label });
      reload();
    } catch {
      setError("Failed to update.");
    }
  }

  async function handleTierChange(value: string, tier: string) {
    try {
      await adminUpdateOption(kind, value, { tier: tier || null });
      reload();
    } catch {
      setError("Failed to update.");
    }
  }

  async function handleDelete(value: string) {
    try {
      await adminDeleteOption(kind, value);
      reload();
    } catch {
      setError("Failed to delete.");
    }
  }

  return (
    <SectionCard title={title}>
      {error && <p className="mb-2 text-xs text-status-strong-concern">{error}</p>}
      {!rows ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.value} className="flex items-center gap-2">
              <span className="w-32 shrink-0 truncate text-xs text-muted-foreground">
                {row.value}
              </span>
              <TextInput
                defaultValue={row.label}
                onBlur={(e) => e.target.value !== row.label && handleLabelChange(row.value, e.target.value)}
                className="flex-1"
              />
              {kind === "companies" && (
                <select
                  defaultValue={row.tier ?? ""}
                  onChange={(e) => handleTierChange(row.value, e.target.value)}
                  className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-foreground"
                >
                  <option value="">No tier</option>
                  {COMPANY_TIERS.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              )}
              <SmallButton variant="danger" onClick={() => handleDelete(row.value)}>
                Delete
              </SmallButton>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex items-center gap-2 border-t border-border pt-3">
        <TextInput placeholder="value (e.g. staff)" value={newValue} onChange={(e) => setNewValue(e.target.value)} className="w-32" />
        <TextInput
          placeholder="label (e.g. Staff)"
          value={newLabel}
          onChange={(e) => setNewLabel(e.target.value)}
          className="flex-1"
        />
        <SmallButton onClick={handleAdd}>Add</SmallButton>
      </div>
    </SectionCard>
  );
}

function DurationsEditor() {
  const [rows, setRows] = useState<AdminDuration[] | null>(null);
  const [newMinutes, setNewMinutes] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reload() {
    adminListDurations()
      .then(setRows)
      .catch(() => setError("Failed to load."));
  }

  useEffect(reload, []);

  async function handleAdd() {
    const minutes = parseInt(newMinutes, 10);
    if (!minutes || minutes <= 0) return;
    setError(null);
    try {
      await adminCreateDuration({ minutes, sort_order: rows?.length ?? 0 });
      setNewMinutes("");
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add.");
    }
  }

  async function handleDelete(minutes: number) {
    try {
      await adminDeleteDuration(minutes);
      reload();
    } catch {
      setError("Failed to delete.");
    }
  }

  return (
    <SectionCard title="Durations">
      {error && <p className="mb-2 text-xs text-status-strong-concern">{error}</p>}
      {!rows ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {rows.map((row) => (
            <li
              key={row.minutes}
              className="flex items-center gap-2 rounded-full border border-border px-3 py-1 text-sm"
            >
              {row.minutes} min
              <button
                type="button"
                onClick={() => handleDelete(row.minutes)}
                className="text-muted-foreground hover:text-status-strong-concern"
              >
                &times;
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex items-center gap-2 border-t border-border pt-3">
        <TextInput
          type="number"
          placeholder="minutes"
          value={newMinutes}
          onChange={(e) => setNewMinutes(e.target.value)}
          className="w-24"
        />
        <SmallButton onClick={handleAdd}>Add</SmallButton>
      </div>
    </SectionCard>
  );
}

function RoundTypesEditor() {
  const [rows, setRows] = useState<AdminRoundType[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    adminListRoundTypes()
      .then(setRows)
      .catch(() => setError("Failed to load."));
  }

  useEffect(reload, []);

  async function handleToggle(value: string, enabled: boolean) {
    try {
      await adminUpdateRoundType(value, { enabled });
      reload();
    } catch {
      setError("Failed to update.");
    }
  }

  return (
    <SectionCard title="Round types">
      <p className="mb-3 text-xs text-muted-foreground">
        Six round types have real interviewers today (Hiring Manager is the one that
        doesn&apos;t yet). This toggle is cosmetic only - it does not gate whether a round
        type has a real interviewer or shows up on Practice; that&apos;s controlled in the
        frontend&apos;s round type config, not here.
      </p>
      {error && <p className="mb-2 text-xs text-status-strong-concern">{error}</p>}
      {!rows ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.value} className="flex items-center justify-between">
              <span className="text-sm text-foreground">{row.label}</span>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={row.enabled}
                  onChange={(e) => handleToggle(row.value, e.target.checked)}
                />
                Enabled
              </label>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function StudyResourcesEditor() {
  const [rows, setRows] = useState<AdminStudyResource[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ dimension: "", title: "", url: "", note: "", kind: "link" });

  function reload() {
    adminListStudyResources()
      .then(setRows)
      .catch(() => setError("Failed to load."));
  }

  useEffect(reload, []);

  async function handleAdd() {
    if (!form.dimension.trim() || !form.title.trim()) return;
    setError(null);
    try {
      await adminCreateStudyResource({
        dimension: form.dimension.trim(),
        title: form.title.trim(),
        url: form.url.trim() || null,
        note: form.note.trim() || null,
        kind: form.kind,
      });
      setForm({ dimension: "", title: "", url: "", note: "", kind: "link" });
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add.");
    }
  }

  async function handleDelete(id: string) {
    try {
      await adminDeleteStudyResource(id);
      reload();
    } catch {
      setError("Failed to delete.");
    }
  }

  async function handleFieldBlur(row: AdminStudyResource, field: "title" | "url" | "note", value: string) {
    if (value === (row[field] ?? "")) return;
    try {
      await adminUpdateStudyResource(row.id, { [field]: value || null });
      reload();
    } catch {
      setError("Failed to update.");
    }
  }

  const grouped = new Map<string, AdminStudyResource[]>();
  for (const r of rows ?? []) {
    if (!grouped.has(r.dimension)) grouped.set(r.dimension, []);
    grouped.get(r.dimension)!.push(r);
  }

  return (
    <SectionCard title="Study resources">
      <p className="mb-3 text-xs text-muted-foreground">
        Powers the &quot;Next suggested action&quot; section on /report - curated by you, not
        AI-generated. Empty on purpose until you add resources here.
      </p>
      {error && <p className="mb-2 text-xs text-status-strong-concern">{error}</p>}
      {!rows ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="mb-3 text-sm text-muted-foreground">No resources added yet.</p>
      ) : (
        <div className="mb-4 space-y-4">
          {Array.from(grouped.entries()).map(([dimension, items]) => (
            <div key={dimension}>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {dimension}
              </p>
              <ul className="space-y-2">
                {items.map((r) => (
                  <li key={r.id} className="flex items-center gap-2">
                    <span className="w-16 shrink-0 text-xs text-muted-foreground">{r.kind}</span>
                    <TextInput
                      defaultValue={r.title}
                      onBlur={(e) => handleFieldBlur(r, "title", e.target.value)}
                      className="flex-1"
                    />
                    <TextInput
                      defaultValue={r.url ?? ""}
                      placeholder="url"
                      onBlur={(e) => handleFieldBlur(r, "url", e.target.value)}
                      className="flex-1"
                    />
                    <SmallButton variant="danger" onClick={() => handleDelete(r.id)}>
                      Delete
                    </SmallButton>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      <div className="grid grid-cols-1 gap-2 border-t border-border pt-3 sm:grid-cols-2">
        <input list="dimension-suggestions" placeholder="dimension" value={form.dimension}
          onChange={(e) => setForm({ ...form, dimension: e.target.value })}
          className="rounded-md border border-border bg-surface px-2 py-1 text-sm text-foreground" />
        <datalist id="dimension-suggestions">
          {DIMENSION_SUGGESTIONS.map((d) => (
            <option key={d.key} value={d.key}>
              {d.label}
            </option>
          ))}
        </datalist>
        <select
          value={form.kind}
          onChange={(e) => setForm({ ...form, kind: e.target.value })}
          className="rounded-md border border-border bg-surface px-2 py-1 text-sm text-foreground"
        >
          <option value="link">Link</option>
          <option value="book">Book</option>
          <option value="course">Course</option>
          <option value="paper">Paper</option>
          <option value="video">Video</option>
        </select>
        <TextInput placeholder="title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <TextInput placeholder="url (optional)" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
        <TextInput
          placeholder="note (optional)"
          value={form.note}
          onChange={(e) => setForm({ ...form, note: e.target.value })}
          className="sm:col-span-2"
        />
        <div className="sm:col-span-2">
          <SmallButton onClick={handleAdd}>Add resource</SmallButton>
        </div>
      </div>
    </SectionCard>
  );
}

// Backs Progress's "Next suggested action" panel (3 fixed subsections -
// Substack for breadth/depth, the not-yet-live class, 1:1 consulting), one
// editor per known key (apps/api/routes/admin.py::_KNOWN_SETTING_KEYS) so
// each link can be updated here without a code change - e.g. once the class
// actually has a signup URL.
function SingleSettingEditor({
  settingKey,
  title,
  helpText,
  placeholder,
}: {
  settingKey: string;
  title: string;
  helpText: string;
  placeholder: string;
}) {
  const [url, setUrl] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminListSettings()
      .then((rows) => {
        const row = rows.find((r) => r.key === settingKey);
        setUrl(row?.value ?? "");
      })
      .catch(() => setError("Failed to load."));
  }, [settingKey]);

  async function handleSave() {
    setError(null);
    setSaved(false);
    try {
      await adminUpdateSetting(settingKey, url.trim() || null);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save.");
    }
  }

  return (
    <SectionCard title={title}>
      <p className="mb-3 text-xs text-muted-foreground">{helpText}</p>
      {error && <p className="mb-2 text-xs text-status-strong-concern">{error}</p>}
      <div className="flex items-center gap-2">
        <TextInput
          placeholder={placeholder}
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            setSaved(false);
          }}
          className="flex-1"
        />
        <SmallButton onClick={handleSave}>Save</SmallButton>
        {saved && <span className="text-xs text-status-strong-positive">Saved.</span>}
      </div>
    </SectionCard>
  );
}

function SettingsEditor() {
  return (
    <>
      <SingleSettingEditor
        settingKey="substack_url"
        title="Substack link (Develop breadth and depth)"
        helpText={`Shown on candidates' Progress page under "Develop breadth and depth". Opens in a new tab.`}
        placeholder="https://pawankjha.substack.com/"
      />
      <SingleSettingEditor
        settingKey="class_url"
        title="Class link (Develop core competency)"
        helpText={`Shown on candidates' Progress page under "Develop core competency". Leave blank to show "Coming soon".`}
        placeholder="https://..."
      />
      <SingleSettingEditor
        settingKey="consultancy_booking_url"
        title="Consultancy booking link (Talk to expert)"
        helpText={`Shown on candidates' Progress page under "Talk to expert". Opens in a new tab.`}
        placeholder="https://calendly.com/..."
      />
    </>
  );
}

const FEEDBACK_KIND_LABEL: Record<AdminFeedback["kind"], string> = {
  feedback: "Feedback",
  issue: "Issue",
  advice: "Advice",
};

// Read-only by design (see apps/api/models.py's Feedback docstring) - for a
// handful of pilot testers, reading straight through is simpler than
// building status/triage workflow nobody's asked for yet.
function FeedbackSection() {
  const [rows, setRows] = useState<AdminFeedback[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminListFeedback()
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load."));
  }, []);

  return (
    <SectionCard title="Feedback from testers">
      <p className="mb-3 text-xs text-muted-foreground">
        Submitted via the floating &quot;Feedback&quot; button shown throughout the app. Newest first.
      </p>
      {error && <p className="mb-2 text-xs text-status-strong-concern">{error}</p>}
      {!rows ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No feedback submitted yet.</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.id} className="rounded-md border border-border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="rounded-full border border-border px-2 py-0.5 text-xs font-medium text-foreground">
                    {FEEDBACK_KIND_LABEL[r.kind] ?? r.kind}
                  </span>
                  <span className="text-sm font-medium text-foreground">{r.user_name}</span>
                  <span className="text-xs text-muted-foreground">{r.user_email}</span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {new Date(r.created_at).toLocaleString()}
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-foreground">{r.message}</p>
              {r.page_path && (
                <p className="mt-1.5 text-xs text-muted-foreground">From {r.page_path}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    me()
      .then((u) => {
        setUser(u);
        if (!u.is_admin) router.push("/dashboard");
      })
      .catch(() => router.push("/login"))
      .finally(() => setChecked(true));
  }, [router]);

  if (!checked || !user?.is_admin) {
    return null;
  }

  return (
    <AppShell user={user} active="admin">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-foreground">Admin</h1>
          <p className="mt-1 text-base text-muted-foreground">
            Manage dropdown options, round types, study resources, and the consultancy link.
          </p>
        </div>
        <div className="space-y-4">
          {OPTION_SECTIONS.map((section) => (
            <OptionListEditor key={section.kind} kind={section.kind} title={section.title} />
          ))}
          <DurationsEditor />
          <RoundTypesEditor />
          <StudyResourcesEditor />
          <SettingsEditor />
          <FeedbackSection />
        </div>
      </div>
    </AppShell>
  );
}
