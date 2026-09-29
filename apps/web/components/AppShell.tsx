"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import Logo from "@/components/Logo";
import QuotaPill from "@/components/QuotaPill";
import ThemeToggle from "@/components/ThemeToggle";
import { logout, type User } from "@/lib/api";

interface AppShellProps {
  user: User | null;
  active?: "home" | "loops" | "practice" | "loop-planner" | "profile" | "progress" | "intel" | "admin" | "other";
  children: React.ReactNode;
}

// Trimmed primary navigation (specs/003-premium-uiux-redesign section 3) -
// Reports/Evidence/Replay/Drills/Level Calibration deliberately stay OUT of
// top-level nav; they're contextual surfaces reached from within Home/
// Progress, not their own tabs. Loop Planner isn't in the source doc's nav
// list either - kept reachable via a link from the Practice (Setup) page
// instead of a top-level tab, rather than deleted.
const BASE_NAV_ITEMS: { key: AppShellProps["active"]; label: string; href: string }[] = [
  { key: "home", label: "Home", href: "/dashboard" },
  { key: "loops", label: "My Loops", href: "/loops" },
  { key: "practice", label: "Practice", href: "/practice" },
  { key: "progress", label: "Progress", href: "/progress" },
  { key: "intel", label: "Interview Intel", href: "/intel" },
];

export default function AppShell({ user, active, children }: AppShellProps) {
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  // Admin tab only renders for allowlisted admins (user.is_admin, computed
  // fresh server-side on every /v1/auth/me call) - the backend enforces the
  // real gate (apps/api/deps.py::get_current_admin), this is just so a
  // regular candidate never sees the link at all.
  const navItems = user?.is_admin
    ? [...BASE_NAV_ITEMS, { key: "admin" as const, label: "Admin", href: "/admin" }]
    : BASE_NAV_ITEMS;

  return (
    <div className="min-h-screen bg-background">
      {/* No border-b here on purpose - a full-width hairline reads as a
          heavy line now that --border was darkened for WCAG contrast (see
          specs/003-premium-uiux-redesign/CONTRAST_AUDIT.md). Separation from
          the page below comes from the header's own bg-surface against the
          page's bg-background, plus extra vertical padding, not a divider. */}
      {/* Shell widened 1024px -> 1152px (2026-09, user report of unused
          side margins on wide screens). Browse/list pages (Home, My Loops,
          Practice, Admin) use most of that width now (max-w-4xl inner
          container, up from max-w-2xl); pure-reading pages (Progress,
          Setup, Profile, Compare) deliberately kept at max-w-2xl - a long
          line length hurts readability the same way it would in a book or
          article, so widening the shell shouldn't force those pages wider
          too, just give the shell itself more room to work with. */}
      <header className="bg-surface">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <Link href="/dashboard" className="text-foreground">
              <Logo />
            </Link>
            <nav className="flex items-center gap-5">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    // Bumped from text-sm/text-muted-foreground (14px, ~grey)
                    // - user report: nav text read too small and too light.
                    // Both states now use full-strength text-foreground and
                    // differ only by weight (active: semibold), same "color
                    // itself should be crisp, let weight/size do the quiet
                    // vs. loud work" call already made for text-label above -
                    // matches the Linear/Stripe/Notion nav convention this
                    // app is modeled on, rather than tuning the grey value.
                    "text-base text-foreground " + (active === item.key ? "font-semibold" : "font-normal opacity-80 hover:opacity-100")
                  }
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            {user && <QuotaPill user={user} />}
            <Link
              href="/profile"
              className={
                "text-sm " +
                (active === "profile" ? "font-medium text-foreground" : "text-muted-foreground hover:text-foreground")
              }
            >
              {user?.name.split(" ")[0] ?? "Profile"}
            </Link>
            <button onClick={handleLogout} className="text-sm text-muted-foreground hover:text-foreground">
              Sign out
            </button>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
    </div>
  );
}
