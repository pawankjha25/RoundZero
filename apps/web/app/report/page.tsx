"use client";

// /report was renamed to /progress (specs/003-premium-uiux-redesign IA
// update - "Progress" is clearer against /reports/[roundId], a single
// round's report). Kept as a redirect rather than deleted so an old
// bookmark or link still lands somewhere real.
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function LegacyReportRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/progress");
  }, [router]);
  return null;
}
