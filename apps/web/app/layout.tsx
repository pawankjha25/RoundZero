import type { Metadata } from "next";
import FeedbackWidget from "@/components/FeedbackWidget";
import ThemeProvider from "@/components/ThemeProvider";
// Self-hosted variable font (no fonts.googleapis.com network dependency at
// build/runtime - see globals.css --font-sans comment). Defines the
// "Inter Variable" @font-face used as the primary entry in --font-sans -
// fixes capital L being visually misread as I in the OS fallback fonts
// (e.g. "ML System Design" reading as "MI System Design").
import "@fontsource-variable/inter";
import "./globals.css";

export const metadata: Metadata = {
  title: "Round Zero",
  description: "AI-powered full-loop interview simulator",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <ThemeProvider>
          {children}
          {/* Global, outside every page's own AppShell (dashboard/loops/etc.
              all render AppShell themselves, but the interview room -
              app/interview/[roundId]/page.tsx - deliberately doesn't, so
              mounting the widget here instead of inside AppShell is what
              keeps it reachable mid-interview too). */}
          <FeedbackWidget />
        </ThemeProvider>
      </body>
    </html>
  );
}
