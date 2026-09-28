"use client";

// Prep Plans list (user-pitched feature, not from the P0 backlog) - a
// candidate's own self-curated prep plans (e.g. "Staff MLE prep"). Reached
// from the dashboard's "My Prep Plans" link or /practice's card - no
// top-level nav tab of its own, same "contextual surface, not a tab"
// precedent /real-interviews already follows.
import { useEffect, useState, type MouseEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { formatLabel } from "@/lib/format";
import { deletePrepPlan, listPrepPlans, me, type PrepPlan, type User } from "@/lib/api";

export default function PrepPlansPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [plans, setPlans] = useState<PrepPlan[] | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    me()
      .then((u) => {
        setUser(u);
        listPrepPlans()
          .then(setPlans)
          .catch(() => setPlans([]));
      })
      .catch(() => router.push("/login"));
  }, [router]);

  async function handleDeletePlan(e: MouseEvent, plan: PrepPlan) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`Delete "${plan.name}" and everything in it?`)) return;
    setError(null);
    setDeletingId(plan.id);
    try {
      await deletePrepPlan(plan.id);
      setPlans((prev) => (prev ? prev.filter((p) => p.id !== plan.id) : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this plan");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <AppShell user={user} active="practice">
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Prep plans</h1>
            <p className="mt-1 text-base text-muted-foreground">
              Your own curated practice questions, organized by area - pick whatever you&apos;re in the
              mood to practice, instead of a random scenario every time.
            </p>
          </div>
          <Button href="/prep-plans/new" className="shrink-0">
            Create a plan
          </Button>
        </div>

        {error && <p className="text-sm text-status-strong-concern">{error}</p>}

        {plans === null ? null : plans.length === 0 ? (
          <EmptyState
            title="No prep plans yet."
            description="Build a plan around a target role - e.g. 'Staff MLE prep' - then add the specific questions you want to drill, area by area."
            action={
              <Button href="/prep-plans/new">Create your first plan</Button>
            }
          />
        ) : (
          <div className="space-y-2">
            {plans.map((plan) => (
              <Link
                key={plan.id}
                href={`/prep-plans/${plan.id}`}
                className="flex items-center justify-between rounded-md border border-border p-3 hover:border-border-strong"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">{plan.name}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {formatLabel(plan.level)} {formatLabel(plan.role_family)}
                    {plan.domain && ` - ${formatLabel(plan.domain)}`}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={(e) => handleDeletePlan(e, plan)}
                  disabled={deletingId === plan.id}
                  className="shrink-0 text-xs font-medium text-status-strong-concern hover:underline disabled:opacity-50"
                >
                  {deletingId === plan.id ? "Deleting..." : "Delete"}
                </button>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
