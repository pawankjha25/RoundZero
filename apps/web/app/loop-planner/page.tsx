"use client";

// /loop-planner was a hardcoded preview of one specific role config
// (configs/loops/principal_ml_infra.yaml) previewing where multi-round loops
// were headed, before they were real (see git history for the old version).
// Now that they are (specs/002-full-loop-platform P0.1, app/loops/new), the
// real loop builder replaces this preview entirely. Kept as a redirect
// rather than deleted so an old bookmark or link still lands somewhere real.
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function LegacyLoopPlannerRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/loops/new");
  }, [router]);
  return null;
}
