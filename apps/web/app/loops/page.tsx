"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppShell from "@/components/AppShell";
import EmptyState from "@/components/ui/EmptyState";
import { LoopCard } from "@/components/loops/LoopList";
import { deleteLoop, listLoops, me, startPlannedRound, type Loop, type User } from "@/lib/api";

export default function LoopsPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loops, setLoops] = useState<Loop[] | null>(null);
  const [checked, setChecked] = useState(false);
  const [startingId, setStartingId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);

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

  function toggleSelected(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : prev.length >= 2 ? [prev[1], id] : [...prev, id]
    );
  }

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

  async function handleDelete(loopId: string) {
    setDeleteError(null);
    setDeletingId(loopId);
    try {
      await deleteLoop(loopId);
      setLoops((prev) => (prev ? prev.filter((l) => l.id !== loopId) : prev));
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Could not delete this loop");
    } finally {
      setDeletingId(null);
    }
  }

  const evaluatedCount =
    loops?.reduce((sum, l) => sum + l.rounds.filter((r) => r.started?.status === "EVALUATED").length, 0) ?? 0;

  if (!checked) {
    return null;
  }

  return (
    <AppShell user={user} active="loops">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-foreground">My Loops</h1>
            <p className="mt-1 text-base text-muted-foreground">Every loop you&apos;ve created, and what&apos;s in it.</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {evaluatedCount >= 2 && (
              <button
                type="button"
                onClick={() => {
                  if (compareMode) setSelected([]);
                  setCompareMode(!compareMode);
                }}
                className="rounded-md border border-border px-3 py-2 text-sm font-medium text-foreground hover:border-border-strong"
              >
                {compareMode ? "Cancel" : "Compare"}
              </button>
            )}
            <Link
              href="/loops/new"
              className="rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-foreground hover:opacity-90"
            >
              + Create Round Zero
            </Link>
          </div>
        </div>

        {startError && <p className="mb-4 text-sm text-status-strong-concern">{startError}</p>}
        {deleteError && <p className="mb-4 text-sm text-status-strong-concern">{deleteError}</p>}

        {!loops ? null : loops.length === 0 ? (
          <EmptyState
            title="No loops yet."
            description="A loop holds one interview or several - create your first one to see it here."
            action={
              <Link
                href="/loops/new"
                className="inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:opacity-90"
              >
                Create Round Zero
              </Link>
            }
          />
        ) : (
          <>
            {compareMode && (
              <div className="mb-4 flex items-center justify-between rounded-lg border border-border bg-muted px-4 py-3 text-sm">
                <p className="text-muted-foreground">
                  {selected.length === 0
                    ? "Pick two evaluated rounds to compare."
                    : selected.length === 1
                      ? "Pick one more evaluated round."
                      : "Ready to compare."}
                </p>
                {selected.length === 2 && (
                  <Link
                    href={`/compare?a=${selected[0]}&b=${selected[1]}`}
                    className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-foreground hover:opacity-90"
                  >
                    Compare selected
                  </Link>
                )}
              </div>
            )}

            <ul className="space-y-4">
              {loops.map((loop) => (
                <LoopCard
                  key={loop.id}
                  loop={loop}
                  onStart={handleStart}
                  startingId={startingId}
                  onDelete={handleDelete}
                  deletingId={deletingId}
                  compareMode={compareMode}
                  selected={selected}
                  onToggleCompare={toggleSelected}
                />
              ))}
            </ul>
          </>
        )}
      </div>
    </AppShell>
  );
}
