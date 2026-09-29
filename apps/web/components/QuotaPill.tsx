"use client";

// Quota indicator near the username in AppShell's header (pricing-design.md:
// "show near username and then button to upgrade"). Reads entirely off
// User.entitlement, which /v1/auth/me already bundles - no separate network
// call. States mirror the design doc: plenty (quiet) / low (warning) /
// exhausted-or-expired (urgent, filled Upgrade button) / free-trial nearing
// its 7-day deadline (warning + countdown) / paid-and-healthy (mostly
// "Manage plan", only becomes an upsell once low). A very large
// rounds_included (Founding Members' "no practical ceiling" - see
// UserEntitlement's docstring in apps/api/models.py) reads as "Unlimited"
// rather than a literal huge number.
import { useState } from "react";
import Link from "next/link";
import type { User } from "@/lib/api";

const UNLIMITED_THRESHOLD = 1000;

function daysUntil(iso: string): number {
  const ms = new Date(iso).getTime() - Date.now();
  return Math.ceil(ms / (1000 * 60 * 60 * 24));
}

export default function QuotaPill({ user }: { user: User }) {
  const [open, setOpen] = useState(false);
  const { entitlement } = user;
  const { cohort, plan, rounds_included, rounds_used, rounds_remaining, expires_at, is_expired } = entitlement;

  // Hasn't clicked Subscribe yet (pricing-design.md, 2026-09-29 - see
  // apps/web/app/upgrade/page.tsx) - distinct from "exhausted", which implies
  // they once had rounds to run out of.
  const isUnsubscribed = plan === "unselected";
  const isUnlimited = rounds_included >= UNLIMITED_THRESHOLD;
  const isFreeCohort = plan === "none";
  const daysLeft = expires_at ? daysUntil(expires_at) : null;

  let tone: "quiet" | "warning" | "urgent" = "quiet";
  if (isUnsubscribed) {
    tone = "warning";
  } else if (!isUnlimited && (is_expired || rounds_remaining <= 0)) {
    tone = "urgent";
  } else if (!isUnlimited && (rounds_remaining <= 2 || rounds_remaining / Math.max(1, rounds_included) <= 0.2)) {
    tone = "warning";
  } else if (isFreeCohort && daysLeft !== null && daysLeft <= 2) {
    tone = "warning";
  }

  const toneTextClass =
    tone === "urgent"
      ? "text-[color:var(--status-strong-concern)]"
      : tone === "warning"
        ? "text-[color:var(--status-neutral)]"
        : "text-muted-foreground";

  const label = isUnsubscribed
    ? "Subscribe to start"
    : isUnlimited
      ? "Unlimited rounds"
      : is_expired
        ? "Trial ended"
        : `${rounds_remaining}/${rounds_included} round${rounds_included === 1 ? "" : "s"} left`;

  // Paid + healthy: mostly stays out of the way ("Manage plan" only).
  // Everyone else (free trial, tester, or a paid plan running low) gets a
  // real Upgrade call to action.
  const isHealthyPaidPlan = cohort === "paid" && tone === "quiet";

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className={`text-sm font-medium ${toneTextClass} hover:underline`}
      >
        {label}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-64 rounded-md border border-border bg-surface p-4 shadow-lg">
          {isUnsubscribed ? (
            <p className="text-sm text-muted-foreground">
              You haven&apos;t picked a plan yet - even the free one only takes a click.
            </p>
          ) : (
            <>
              <p className="text-sm font-medium capitalize text-foreground">
                {plan === "none" ? "Free trial" : plan} plan
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {isUnlimited ? "No practical round limit." : `${rounds_used} of ${rounds_included} rounds used this period.`}
              </p>
              {isFreeCohort && daysLeft !== null && (
                <p className="mt-1 text-sm text-muted-foreground">
                  {daysLeft > 0
                    ? `${daysLeft} day${daysLeft === 1 ? "" : "s"} left in your free trial.`
                    : "Your free trial has ended."}
                </p>
              )}
            </>
          )}
          <Link
            href="/upgrade"
            className={
              "mt-3 block rounded-md px-3 py-1.5 text-center text-sm font-medium " +
              (isHealthyPaidPlan
                ? "border border-border text-foreground hover:bg-muted"
                : "bg-accent text-accent-foreground hover:opacity-90")
            }
          >
            {isUnsubscribed ? "Subscribe" : isHealthyPaidPlan ? "Manage plan" : "Upgrade"}
          </Link>
        </div>
      )}
    </div>
  );
}
