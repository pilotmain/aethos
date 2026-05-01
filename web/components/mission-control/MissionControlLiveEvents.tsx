"use client";

import { useEffect, useState } from "react";
import { DEFAULT_API_BASE, readConfig } from "@/lib/config";

function toWsOrigin(httpBase: string): string {
  try {
    const u = new URL(httpBase.startsWith("http") ? httpBase : `http://${httpBase}`);
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    return u.origin;
  } catch {
    return "ws://127.0.0.1:8010";
  }
}

/**
 * Minimal live event stream for Nexa Next runtime (Phase 7).
 * Subscribes to the API WebSocket and appends JSON events (mission / task / artifact).
 */
export function MissionControlLiveEvents() {
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);
  const [wsUrl, setWsUrl] = useState<string>("");

  useEffect(() => {
    const c = readConfig();
    const base = c.apiBase?.trim() || DEFAULT_API_BASE;
    const url = `${toWsOrigin(base)}/api/v1/mission-control/events/ws`;
    setWsUrl(url);

    const ws = new WebSocket(url);
    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as Record<string, unknown>;
        setEvents((prev) => [...prev, event].slice(-500));
      } catch {
        /* ignore non-JSON */
      }
    };

    const ping = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 25_000);

    return () => {
      clearInterval(ping);
      ws.close();
    };
  }, []);

  return (
    <section className="border-b border-zinc-800 bg-zinc-950/80 px-4 py-3">
      <h2 className="text-sm font-medium text-zinc-200">Live execution</h2>
      <p className="truncate text-xs text-zinc-500" title={wsUrl}>
        {wsUrl || "Connecting…"} · {events.length} events
      </p>
      <div className="mt-2 max-h-52 overflow-auto rounded border border-zinc-800 bg-black/40 font-mono text-[11px] leading-snug text-zinc-300">
        {events.map((e, i) => (
          <pre key={i} className="whitespace-pre-wrap border-b border-zinc-900 px-2 py-1.5 last:border-b-0">
            {JSON.stringify(e, null, 2)}
          </pre>
        ))}
      </div>
    </section>
  );
}
