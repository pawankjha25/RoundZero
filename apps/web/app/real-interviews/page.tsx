"use client";

// Real Interview log (specs/002-full-loop-platform P0.11/P0.12) - the
// candidate's own list of interviews they actually went through at real
// companies. Separate from every simulated-round list elsewhere in the app.
// Reached from the dashboard's "Log a real interview" link, a finished
// loop's card, or /intel's CTA - no top-level nav tab of its own, same
// "contextual surface, not a tab" precedent every report/replay/compare page
// here already follows (see AppShell.tsx's docstring).
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import StatusBadge from "@/components/ui/StatusBadge";
import { formatLabel } from "@/lib/format";
import { listRealInterviews, me, type RealInterviewExperience, type User } from "@/lib/api";

const OUTCOME_LABELS: Record<string, string> = {
  rejected: "Rejected",
  advanced: "Advanced",
  offer: "Offer",
  withdrew: "Withdrew",
  no_response: "No response",
};

function outcomeTone(status: string): "strong-positive" | "positive" | "neutral" | "concern" | "strong-concern" {
  if (status === "offer") return "strong-positive";
  if (status === "advanced") return "positive";
  if (status === "no_response" || status === "withdrew") return "neutral";
  return "concern";
}

export default function RealInterviewsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [experiences, setExperiences] = useState<RealInterviewExperience[] | null>(null);

  useEffect(() => {
    me()
      .then((u) => {
        setUser(u);
        listRealInterviews()
          .then(setExperiences)
          .catch(() => setExperiences([]));
      })
      .catch(() => router.push("/login"));
  }, [router]);

  return (
    <AppShell user={user} active="other">
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Real interviews</h1>
            <p className="mt-1 text-base text-muted-foreground">
              Your own log of interviews you&apos;ve actually gone through - question types, difficulty, and
              how it turned out.
            </p>
          </div>
          <Button href="/real-interviews/new" className="shrink-0">
            Log a real interview
          </Button>
        </div>

        {experiences === null ? null : experiences.length === 0 ? (
          <EmptyState
            title="No real interviews logged yet."
            description="After you interview somewhere for real, log it here - the question types and how it went, plus the outcome once you hear back. Round Zero never sees or shares this unless you choose to."
            action={
              <Button href="/real-interviews/new">Log your first one</Button>
            }
          />
        ) : (
          <div className="space-y-2">
            {experiences.map((exp) => (
              <Link
                key={exp.id}
                href={`/real-interviews/${exp.id}`}
                className="flex items-center justify-between rounded-md border border-border p-3 hover:border-border-strong"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {exp.company} - {formatLabel(exp.level)} {formatLabel(exp.role_family)}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {new Date(exp.interview_date).toLocaleDateString()}
                    {exp.domain && ` - ${formatLabel(exp.domain)}`}
                  </p>
                </div>
                {exp.outcome && (
                  <StatusBadge label={OUTCOME_LABELS[exp.outcome.status] ?? exp.outcome.status} tone={outcomeTone(exp.outcome.status)} />
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
