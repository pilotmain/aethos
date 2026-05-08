"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { readConfig } from "@/lib/config";

/**
 * Redirect to Connection settings when Mission Control has no stored API base + user id.
 * Prefer standalone localStorage keys; fall back to merged config (e.g. `aethos_web_v1`).
 */
export function MissionControlAuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const c = readConfig();
    const userId =
      (typeof window !== "undefined" ? window.localStorage.getItem("aethos_user_id") : null)?.trim() ||
      c.userId.trim();
    const apiBase =
      (typeof window !== "undefined" ? window.localStorage.getItem("aethos_api_base") : null)?.trim() ||
      c.apiBase.trim();

    if (!userId || !apiBase) {
      router.push("/login");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-sm text-zinc-400">
        Checking session…
      </div>
    );
  }

  return children;
}
