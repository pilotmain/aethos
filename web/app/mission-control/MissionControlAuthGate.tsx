"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { isConfigured } from "@/lib/config";

/**
 * Ensures browser-local Mission Control credentials exist before rendering MC routes.
 * Phase 80 — avoids silent failures; pairs with login page session redirect.
 */
export function MissionControlAuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isConfigured()) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [pathname, router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-sm text-zinc-400">
        Checking session…
      </div>
    );
  }

  return children;
}
