"use client";

// Thin wrapper around next-themes so app/layout.tsx (a server component) can
// stay a server component while still getting a flash-free, persisted
// light/dark toggle - next-themes injects a blocking inline script into
// <head> that sets the "dark" class (attribute="class", matching
// globals.css's @custom-variant dark) before React hydrates, so there's no
// flash of the wrong theme on load. defaultTheme="system" respects the OS
// preference until the candidate picks one explicitly (ThemeToggle.tsx),
// at which point next-themes persists the choice to localStorage itself.
import { ThemeProvider as NextThemesProvider } from "next-themes";

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem>
      {children}
    </NextThemesProvider>
  );
}
