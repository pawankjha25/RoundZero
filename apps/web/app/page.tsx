"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { me } from "@/lib/api";

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    me()
      .then(() => router.push("/dashboard"))
      .catch(() => router.push("/login"));
  }, [router]);

  return null;
}
