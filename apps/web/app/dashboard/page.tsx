"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import EmptyState from "@/components/ui/EmptyState";
import Button from "@/components/ui/Button";
import { LoopCard, classifyLoop, type LoopStage } from "@/components/loops/LoopList";
import { listLoops, me, startPlannedRound, type Loop, type User } from "@/lib/api";

const SECTIONS: { stage: LoopStage; title: string }[] = [
  { stage: "ongoing", title: "Ongoing" },
  { stage: "upcoming", title: "Upcoming" },
  { stage: "finished", title: "Finished" },
];

const VISIBLE_PER_SECTION = 2;

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loops, setLoops] = useState<Loop[] | null>(null);
  const [checked, setChecked] = useState(false);
  const [startingId, setStartingId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  useEffect(() => {
    me()
      .then((u) => {
        setUser(u);
        listLoops()
          .then(setLoops)
          .catch(() => setLoops([]));
      })
      .catch(() => router.push("/login"))
      .finally(() => setChecked(true));
  }, [router]);

  async function handleStart(loopId: string, plannedRoundId: string) {
    setStartError(null);
    setStartingId(plannedRoundId);
    try {
      const detail = await startPlannedRound(loopId, plannedRoundId);
      router.push(`/interview/${detail.round.id}`);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Could not start this round");
      setStartingId(null);
    }
  }

  const byStage = useMemo(() => {
    const grouped: Record<LoopStage, Loop[]> = { ongoing: [], upcoming: [], finished: [] };
    for (const loop of loops ?? []) {
      grouped[classifyLoop(loop)].push(loop);
    }
    return grouped;
  }, [loops]);

  if (!checked) {
    return null;
  }

  return (
    <AppShell user={user} active="home">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-foreground">
              Welcome back{user ? `, ${user.name.split(" ")[0]}` : ""}
            </h1>
            <p className="mt-1 text-base text-muted-foreground">Where you left off, and what&apos;s next.</p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <Link href="/real-interviews" className="whitespace-nowrap text-sm text-accent hover:underline">
              Log a real interview &rarr;
            </Link>
            <Link href="/prep-plans" className="whitespace-nowrap text-sm text-accent hover:underline">
              My prep plans &rarr;
            </Link>
          </div>
        </div>

        {startError && <p className="mb-4 text-sm text-status-strong-concern">{startError}</p>}

        {!loops ? null : loops.length === 0 ? (
          <EmptyState
            title="Your interview trajectory starts here."
            description="Create your first loop to establish your baseline."
            action={
              <Button href="/loops/new">Create Round Zero</Button>
            }
          />
        ) : (
          <div className="space-y-8">
            {SECTIONS.map(({ stage, title }) => {
              const sectionLoops = byStage[stage];
              if (sectionLoops.length === 0) return null;
              const visible = sectionLoops.slice(0, VISIBLE_PER_SECTION);
              const remaining = sectionLoops.length - visible.length;
              return (
                <div key={stage}>
                  <h2 className="mb-3 text-sm font-semibold text-foreground">{title}</h2>
                  <ul className="space-y-3">
                    {visible.map((loop) => (
                      <LoopCard
                        key={loop.id}
                        loop={loop}
                        onStart={handleStart}
                        startingId={startingId}
                        defaultExpanded={stage === "ongoing" && visible.length === 1}
                      />
                    ))}
                  </ul>
                  {remaining > 0 && (
                    <p className="mt-2 text-sm">
                      <Link href="/loops" className="text-accent hover:underline">
                        View all ({remaining} more) &rarr;
                      </Link>
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
