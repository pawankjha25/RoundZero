"use client";

// Subscribe / plans page (pricing-design.md "UI reference" + the Subscribe
// gate added 2026-09-29: "let the user login - don't give them automatically
// ... for any practice they need to subscribe ... Plan None/Free is where
// they get one test"). A brand-new self-signup account starts with
// plan="unselected" and 0 rounds (apps/api/deps.py::_ensure_entitlement) -
// nothing to practice with until they pick a plan here. None/Free (POST
// /v1/auth/subscribe -> orchestrator.select_plan) and Pay-per-loop (Stripe
// Checkout, Phase 2 - see lib/api.ts::createCheckoutSession) both actually
// work now. Monthly/Yearly/Founding Members are Phase 3 (subscriptions via
// Stripe Billing) - not built - so those three cards stay disabled/"Coming
// soon", matching the original 5-card layout from the design doc.
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { createCheckoutSession, me, subscribe, type PayPerLoopPack, type User } from "@/lib/api";

interface PlanCard {
  key: string;
  name: string;
  price: string;
  tagline: string;
  features: string[];
  available: boolean;
}

const PLANS: PlanCard[] = [
  {
    key: "none",
    name: "None",
    price: "$0",
    tagline: "1 free round (any type) · 7 days to use it",
    features: ["1 round of any type you pick", "Full evaluation + report", "7-day window starts when you subscribe"],
    available: true,
  },
  {
    key: "monthly",
    name: "Monthly",
    price: "$49–69/mo",
    tagline: "~4–5 loops a month",
    features: ["~16–20 rounds/month", "Any mix of round types", "Cancel anytime"],
    available: false,
  },
  {
    key: "yearly",
    name: "Yearly",
    price: "$490–690/yr",
    tagline: "~17% cheaper than Monthly",
    features: ["Same allowance as Monthly", "Billed once a year"],
    available: false,
  },
  {
    key: "founding",
    name: "Founding Members",
    price: "From $199/yr",
    tagline: "Schedule anytime, no quota limit",
    features: ["No practical round ceiling", "Locked-in rate for life", "Pay-what-you-want, price floor applies"],
    available: false,
  },
];

// Mirrors apps/api/routes/billing.py::PAYPERLOOP_PACKS - two fixed packs,
// no dashboard-configured Stripe Price objects to keep in sync, just these
// literals matching the backend's price_cents.
const PAYPERLOOP_PACKS: { pack: PayPerLoopPack; label: string; price: string }[] = [
  { pack: "pack_4", label: "4 rounds (about 1 loop)", price: "$30" },
  { pack: "pack_12", label: "12 rounds (about 3 loops)", price: "$80" },
];

function UpgradePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [subscribing, setSubscribing] = useState(false);
  const [checkoutPack, setCheckoutPack] = useState<PayPerLoopPack | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => router.push("/login"))
      .finally(() => setChecked(true));
  }, [router]);

  // Stripe Checkout redirects back here with ?checkout=success|cancelled
  // (see createCheckoutSession's success_url/cancel_url in billing.py).
  // "success" needs a fresh me() so the quota pill/plan card reflect the
  // webhook's credit right away - the webhook usually beats the browser's
  // redirect back, but re-fetch defensively either way and say so if it
  // hasn't landed yet rather than claiming it succeeded.
  const checkoutResult = searchParams.get("checkout");
  useEffect(() => {
    if (checkoutResult === "success") {
      me()
        .then(setUser)
        .catch(() => {});
    }
  }, [checkoutResult]);

  async function handleSelectFree() {
    setError(null);
    setSubscribing(true);
    try {
      const entitlement = await subscribe("none");
      setUser((prev) => (prev ? { ...prev, entitlement } : prev));
      router.push("/practice");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not subscribe - try again.");
    } finally {
      setSubscribing(false);
    }
  }

  async function handleBuyPack(pack: PayPerLoopPack) {
    setError(null);
    setCheckoutPack(pack);
    try {
      const { checkout_url } = await createCheckoutSession(pack);
      window.location.assign(checkout_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start checkout - try again.");
      setCheckoutPack(null);
    }
  }

  if (!checked) {
    return null;
  }

  const currentPlan = user?.entitlement.plan;
  const hasSubscribed = currentPlan !== undefined && currentPlan !== "unselected";

  return (
    <AppShell user={user} active="other">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-foreground">Plans &amp; billing</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {hasSubscribed
              ? "You're subscribed - manage or change your plan below."
              : "Pick a plan to get started - even the free one only takes a click."}
          </p>
        </div>

        {checkoutResult === "success" && (
          <p className="mb-4 rounded-md border border-status-strong-ready/40 bg-status-strong-ready/10 px-3 py-2 text-sm text-status-strong-ready">
            Payment received - your rounds are being added now. If your balance below doesn&apos;t update in a few
            seconds, refresh the page.
          </p>
        )}
        {checkoutResult === "cancelled" && (
          <p className="mb-4 rounded-md border border-border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
            Checkout was cancelled - no charge was made.
          </p>
        )}
        {error && <p className="mb-4 text-sm text-status-strong-concern">{error}</p>}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {PLANS.map((plan) => {
            const isCurrent = currentPlan === plan.key;
            // RZ-05 (UI/UX review, 2026-09-29): the "None" card's tagline
            // and features were static marketing copy for the real free
            // tier (1 round / 7 days) - shown as-is even for a tester/
            // dogfooder whose actual "None"-plan entitlement is the more
            // generous, no-expiry cohort grant (pricing-design.md's
            // TESTER_EMAILS allowance). Once it's the signed-in user's
            // actual current plan, show their real numbers instead of the
            // generic pitch.
            const isTesterOnNone = isCurrent && plan.key === "none" && user?.entitlement.cohort === "tester";
            const tagline =
              isTesterOnNone && user
                ? `${user.entitlement.rounds_included} rounds, no expiry (tester access)`
                : plan.tagline;
            const features =
              isTesterOnNone && user
                ? [
                    `${user.entitlement.rounds_remaining} of ${user.entitlement.rounds_included} rounds left`,
                    "Full evaluation + report",
                    "No expiry for tester access",
                  ]
                : plan.features;
            return (
              <div
                key={plan.key}
                className={
                  "flex flex-col rounded-lg border p-4 " +
                  (isCurrent ? "border-accent" : "border-border") +
                  (plan.available ? "" : " opacity-70")
                }
              >
                <p className="text-sm font-semibold text-foreground">{plan.name}</p>
                <p className="mt-1 text-lg font-semibold text-foreground">{plan.price}</p>
                <p className="mt-1 text-xs text-muted-foreground">{tagline}</p>
                <ul className="mt-3 flex-1 space-y-1.5">
                  {features.map((f) => (
                    <li key={f} className="text-xs text-muted-foreground">
                      ✓ {f}
                    </li>
                  ))}
                </ul>
                {isCurrent ? (
                  <button
                    type="button"
                    disabled
                    className="mt-4 rounded-md border border-border px-3 py-1.5 text-center text-sm font-medium text-muted-foreground"
                  >
                    Your current plan
                  </button>
                ) : plan.key === "none" ? (
                  <button
                    type="button"
                    onClick={handleSelectFree}
                    disabled={subscribing}
                    className="mt-4 rounded-md bg-accent px-3 py-1.5 text-center text-sm font-medium text-accent-foreground hover:opacity-90 disabled:opacity-50"
                  >
                    {subscribing ? "Starting..." : "Start free"}
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled
                    title="Not connected yet - reach out directly if you'd like this plan now."
                    className="mt-4 rounded-md border border-dashed border-border px-3 py-1.5 text-center text-sm font-medium text-muted-foreground"
                  >
                    Coming soon
                  </button>
                )}
              </div>
            );
          })}

          <div className="flex flex-col rounded-lg border border-border p-4">
            <p className="text-sm font-semibold text-foreground">Pay-per-loop</p>
            <p className="mt-1 text-lg font-semibold text-foreground">From $30</p>
            <p className="mt-1 text-xs text-muted-foreground">No subscription - just buy rounds</p>
            <ul className="mt-3 space-y-1.5">
              <li className="text-xs text-muted-foreground">✓ One-time purchase</li>
              <li className="text-xs text-muted-foreground">✓ No expiry</li>
            </ul>
            <div className="mt-4 flex-1 space-y-2">
              {PAYPERLOOP_PACKS.map((p) => (
                <button
                  key={p.pack}
                  type="button"
                  onClick={() => handleBuyPack(p.pack)}
                  disabled={checkoutPack !== null}
                  className="flex w-full items-center justify-between rounded-md border border-border px-3 py-1.5 text-left text-xs font-medium text-foreground hover:border-accent disabled:opacity-50"
                >
                  <span>{p.label}</span>
                  <span>{checkoutPack === p.pack ? "Redirecting..." : p.price}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {user && hasSubscribed && (
          <p className="mt-6 text-sm text-muted-foreground">
            {user.entitlement.rounds_remaining} of {user.entitlement.rounds_included} rounds left this period.
          </p>
        )}
      </div>
    </AppShell>
  );
}

export default function UpgradePage() {
  return (
    <Suspense fallback={null}>
      <UpgradePageContent />
    </Suspense>
  );
}
