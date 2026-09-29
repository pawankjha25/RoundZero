"use client";

import { useSyncExternalStore } from "react";
import { useTheme } from "next-themes";

// Client-mount detector with no setState-in-effect at all (the previous
// `useState(false)` + `useEffect(() => setMounted(true), [])` version hit
// the react-hooks/set-state-in-effect rule, even though it's the exact
// pattern next-themes' own docs recommend for this). useSyncExternalStore
// needs no subscription here - mount status never changes again once true,
// so `subscribe` is a permanent no-op - it just returns the server snapshot
// (false) during SSR/hydration and the client snapshot (true) once mounted,
// which is the whole point: differ once, then never re-notify.
function useIsMounted(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );
}

// Explicit two-state light/dark toggle (not a three-way incl. "system") -
// simplest predictable behavior: it always shows what the page currently
// looks like and flips it. ThemeProvider still defaults to "system" until
// the candidate clicks this once, at which point next-themes persists their
// explicit choice to localStorage and system changes stop affecting it.
export default function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // next-themes can't know the real theme on the server (it depends on
  // localStorage/matchMedia, both client-only) - rendering a fixed-size
  // placeholder until mounted avoids a hydration mismatch and keeps the
  // header from jumping when the real icon appears a tick later.
  const mounted = useIsMounted();

  if (!mounted) {
    return <span className="inline-block h-8 w-8" aria-hidden="true" />;
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className="flex h-8 w-8 items-center justify-center rounded-md border border-neutral-300 text-neutral-600 hover:bg-neutral-100 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800"
    >
      {isDark ? (
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <g stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" fill="none">
            <circle cx="12" cy="12" r="4.25" />
            <path d="M12 2.5v2.5M12 19v2.5M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M2.5 12H5M19 12h2.5M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" />
          </g>
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path
            d="M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11Z"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      )}
    </button>
  );
}
