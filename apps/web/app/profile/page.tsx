"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import { getProfile, me, updateProfile, type Profile, type User } from "@/lib/api";

const EMPTY_FORM = {
  current_role: "",
  target_role: "",
  years_experience: "",
  experience_summary: "",
  objective: "",
  linkedin_url: "",
};

type FormState = typeof EMPTY_FORM;

function toForm(profile: Profile): FormState {
  return {
    current_role: profile.current_role ?? "",
    target_role: profile.target_role ?? "",
    years_experience: profile.years_experience !== null ? String(profile.years_experience) : "",
    experience_summary: profile.experience_summary ?? "",
    objective: profile.objective ?? "",
    linkedin_url: profile.linkedin_url ?? "",
  };
}

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedJustNow, setSavedJustNow] = useState(false);

  useEffect(() => {
    me()
      .then((u) => {
        setUser(u);
        getProfile()
          .then((p) => {
            setForm(toForm(p));
            setUpdatedAt(p.updated_at);
          })
          .catch(() => {
            /* No profile saved yet - the blank form is already the right state. */
          });
      })
      .catch(() => router.push("/login"))
      .finally(() => setChecked(true));
  }, [router]);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSavedJustNow(false);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const years = form.years_experience.trim();
      const saved = await updateProfile({
        current_role: form.current_role.trim() || null,
        target_role: form.target_role.trim() || null,
        years_experience: years ? Number(years) : null,
        experience_summary: form.experience_summary.trim() || null,
        objective: form.objective.trim() || null,
        linkedin_url: form.linkedin_url.trim() || null,
      });
      setForm(toForm(saved));
      setUpdatedAt(saved.updated_at);
      setSavedJustNow(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your profile");
    } finally {
      setSaving(false);
    }
  }

  if (!checked) {
    return null;
  }

  return (
    <AppShell user={user} active="profile">
      <div className="mx-auto max-w-lg">
        <h1 className="mb-1 text-xl font-semibold text-foreground">Your profile</h1>
        <p className="mb-8 text-base text-muted-foreground">
          A few details about where you are and what you&apos;re aiming for. This is separate from
          the role/level you pick each time you start an interview - it stays with you across every
          round, and helps set the context for your prep.
        </p>

        <form onSubmit={handleSubmit} className="space-y-5">
          <Field
            label="Current role"
            placeholder="e.g. Senior ML Engineer at Acme"
            value={form.current_role}
            onChange={(v) => set("current_role", v)}
          />

          <Field
            label="Target role"
            placeholder="e.g. Staff ML Engineer at a large tech company"
            value={form.target_role}
            onChange={(v) => set("target_role", v)}
          />

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">Years of experience</label>
            <input
              type="number"
              min={0}
              max={60}
              inputMode="numeric"
              value={form.years_experience}
              onChange={(e) => set("years_experience", e.target.value)}
              placeholder="e.g. 6"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
          </div>

          <TextArea
            label="Experience summary"
            placeholder="Briefly describe your background - what you've built, teams you've worked on, the kind of problems you've solved."
            value={form.experience_summary}
            onChange={(v) => set("experience_summary", v)}
          />

          <TextArea
            label="Objective"
            placeholder="What are you preparing for right now, and why? e.g. Aiming for a Staff-level move in the next two quarters, want to shore up reliability/monitoring depth."
            value={form.objective}
            onChange={(v) => set("objective", v)}
          />

          <div>
            <label className="mb-1 block text-sm font-medium text-foreground">
              LinkedIn profile{" "}
              <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <input
              type="url"
              value={form.linkedin_url}
              onChange={(e) => set("linkedin_url", e.target.value)}
              placeholder="https://www.linkedin.com/in/..."
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Just saved for now - a future update may use this to better tailor scenarios and
              feedback to your real background. Nothing is fetched from it today.
            </p>
          </div>

          {error && <p className="text-sm text-status-strong-concern">{error}</p>}

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save profile"}
            </Button>
            {savedJustNow && <span className="text-sm text-status-strong-positive">Saved.</span>}
            {!savedJustNow && updatedAt && (
              <span className="text-xs text-muted-foreground">
                Last saved {new Date(updatedAt).toLocaleString()}
              </span>
            )}
          </div>
        </form>
      </div>
    </AppShell>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-foreground">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
      />
    </div>
  );
}

function TextArea({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-foreground">{label}</label>
      <textarea
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-accent focus:outline-none"
      />
    </div>
  );
}
