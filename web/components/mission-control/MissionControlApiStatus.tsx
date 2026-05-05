"use client";

import { useEffect, useState } from "react";

import { DEFAULT_API_BASE, readConfig } from "@/lib/config";

export function MissionControlApiStatus() {
  const [status, setStatus] = useState<"checking" | "ok" | "error">("checking");

  useEffect(() => {
    let cancelled = false;

    const ping = async () => {
      try {
        const base = readConfig().apiBase || DEFAULT_API_BASE;
        const url = `${base.replace(/\/$/, "")}/api/v1/health`;
        const ac = new AbortController();
        const timer = window.setTimeout(() => ac.abort(), 8000);
        const r = await fetch(url, { cache: "no-store", signal: ac.signal });
        window.clearTimeout(timer);
        if (!cancelled) setStatus(r.ok ? "ok" : "error");
      } catch {
        if (!cancelled) setStatus("error");
      }
    };

    void ping();
    const id = window.setInterval(ping, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (status === "checking") {
    return <p className="text-xs text-zinc-500">API: checking…</p>;
  }
  if (status === "ok") {
    return <p className="text-xs text-emerald-400">API: connected</p>;
  }
  return <p className="text-xs text-amber-400">API: unreachable — check Login → Connection</p>;
}
