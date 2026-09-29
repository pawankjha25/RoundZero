"use client";

// Practice landing (specs/003-premium-uiux-redesign IA update, user-proposed
// nav) - picking WHAT to practice, distinct from configuring a round.
// app/setup/page.tsx is now step 2 (role/level/company/duration/format for
// the chosen round type), reached from here rather than being the landing
// page itself.
//
// "Recommended for you" (a weakness-targeted drill card) is deliberately
// left out - it needs spec 002 P0.10's drill generator, which doesn't exist
// yet. Showing a fake recommendation would be worse than showing none.
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import RoundTypeIcon, { type RoundTypeKey } from "@/components/RoundTypeIcon";
import { me, type User } from "@/lib/api";

const COMING_SOON_ROUNDS: { key: RoundTypeKey; label: string }[] = [
  { key: "hiring_manager", label: "Hiring Manager" },
];

export default function PracticePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    me()
      .then((u) => {
        setUser(u);
        // Subscribe gate (pricing-design.md, 2026-09-29) - Practice is the
        // hub every round-starting path is reached from, so this is the
        // earliest, friendliest place to redirect someone who hasn't picked
        // a plan yet (before they even pick a round type).
        if (u.entitlement.plan === "unselected") {
          router.push("/upgrade");
        }
      })
      .catch(() => router.push("/login"));
  }, [router]);

  return (
    <AppShell user={user} active="practice">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8">
          <h1 className="text-xl font-semibold text-foreground">Practice</h1>
          <p className="mt-1 text-base text-muted-foreground">
            Standalone rounds to build a specific skill - not a full loop.
          </p>
        </div>

        <Link
          href="/prep-plans"
          className="mb-8 flex items-center justify-between rounded-lg border border-border bg-surface p-4 hover:border-border-strong"
        >
          <span>
            <span className="block text-sm font-medium text-foreground">My prep plans</span>
            <span className="block text-sm text-muted-foreground">
              Your own curated practice questions, organized by area - pick what you&apos;re in the mood
              to practice instead of a random scenario.
            </span>
          </span>
          <span className="shrink-0 text-sm text-accent">Open &rarr;</span>
        </Link>

        <h2 className="mb-3 text-sm font-semibold text-foreground">Practice a round</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <Link
            href="/setup"
            className="flex flex-col items-start gap-2 rounded-lg border border-border bg-surface p-4 hover:border-border-strong"
          >
            <RoundTypeIcon type="ml_system_design" className="text-foreground" />
            <span className="text-sm font-medium text-foreground">ML System Design</span>
          </Link>
          <Link
            href="/setup?type=coding"
            className="flex flex-col items-start gap-2 rounded-lg border border-border bg-surface p-4 hover:border-border-strong"
          >
            <RoundTypeIcon type="coding" className="text-foreground" />
            <span className="text-sm font-medium text-foreground">Coding</span>
          </Link>
          <Link
            href="/setup?type=ml_depth"
            className="flex flex-col items-start gap-2 rounded-lg border border-border bg-surface p-4 hover:border-border-strong"
          >
            <RoundTypeIcon type="ml_depth" className="text-foreground" />
            <span className="text-sm font-medium text-foreground">ML Depth</span>
          </Link>
          <Link
            href="/setup?type=backend_system_design"
            className="flex flex-col items-start gap-2 rounded-lg border border-border bg-surface p-4 hover:border-border-strong"
          >
            <RoundTypeIcon type="backend_system_design" className="text-foreground" />
            <span className="text-sm font-medium text-foreground">Backend System Design</span>
          </Link>
          <Link
            href="/setup?type=technical_leadership"
            className="flex flex-col items-start gap-2 rounded-lg border border-border bg-surface p-4 hover:border-border-strong"
          >
            <RoundTypeIcon type="technical_leadership" className="text-foreground" />
            <span className="text-sm font-medium text-foreground">Technical Leadership</span>
          </Link>
          <Link
            href="/setup?type=xfn"
            className="flex flex-col items-start gap-2 rounded-lg border border-border bg-surface p-4 hover:border-border-strong"
          >
            <RoundTypeIcon type="xfn" className="text-foreground" />
            <span className="text-sm font-medium text-foreground">Cross-functional</span>
          </Link>
          {COMING_SOON_ROUNDS.map((r) => (
            <div
              key={r.key}
              className="flex flex-col items-start gap-2 rounded-lg border border-dashed border-border p-4 opacity-60"
            >
              <RoundTypeIcon type={r.key} className="text-muted-foreground" />
              <span className="text-sm font-medium text-muted-foreground">{r.label}</span>
              <span className="text-xs text-muted-foreground">Coming soon</span>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
