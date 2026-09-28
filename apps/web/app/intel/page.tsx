"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import EmptyState from "@/components/ui/EmptyState";
import Button from "@/components/ui/Button";
import { listRealInterviews, me, type User } from "@/lib/api";

// Interview Intel (specs/003-premium-uiux-redesign section 27) - the doc is
// explicit: "create the information architecture now even if data is
// initially sparse." The real-interview capture flow now exists
// (specs/002-full-loop-platform P0.11/P0.12, apps/web/app/real-interviews/) -
// but cross-candidate aggregation into "what to expect at company X" still
// doesn't, since that needs moderation/sanitization infra this repo
// explicitly doesn't have yet (see tasks.md's cross-cutting section). So
// this stays an honest placeholder: it shows the candidate their own logged
// count instead of an always-empty state now that logging is real, but
// still never fabricates cross-candidate trends.
export default function InterviewIntelPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [loggedCount, setLoggedCount] = useState<number | null>(null);

  useEffect(() => {
    me()
      .then((u) => {
        setUser(u);
        listRealInterviews()
          .then((exps) => setLoggedCount(exps.length))
          .catch(() => setLoggedCount(0));
      })
      .catch(() => router.push("/login"))
      .finally(() => setChecked(true));
  }, [router]);

  if (!checked) {
    return null;
  }

  return (
    <AppShell user={user} active="intel">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-foreground">Interview Intel</h1>
          <p className="mt-1 text-base text-muted-foreground">
            What to expect at a given company/role, based on real interview reports.
          </p>
        </div>
        {loggedCount !== null && loggedCount > 0 ? (
          <EmptyState
            title={`You've logged ${loggedCount} real interview${loggedCount === 1 ? "" : "s"}.`}
            description="Full company/role intelligence needs real interview reports from many candidates, not just your own - this page fills in once there's enough data across candidates to summarize responsibly."
            action={
              <Button href="/real-interviews">View your real interviews</Button>
            }
          />
        ) : (
          <EmptyState
            title="Not enough reports yet to show intelligence."
            description="Interview Intel is built from candidates logging real interview experiences (company, round types, question families, difficulty). Log your own to get started - once enough candidates have, this page fills in with what recent candidates reported for each company and role."
            action={
              <Button href="/real-interviews/new">Log a real interview</Button>
            }
          />
        )}
      </div>
    </AppShell>
  );
}
