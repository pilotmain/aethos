"use client";

import { useEffect, useMemo, useState } from "react";
import { missionControlEventsWsUrl } from "@/lib/mission-control/eventsWsUrl";
import {
  connectReconnectingMissionWs,
  type MissionWsConnectionState,
} from "@/lib/ws/reconnectingMissionWs";

/**
 * Live event stream for Nexa Next runtime.
 * Subscribes to the API WebSocket with reconnect backoff (Phase 11).
 */
export function MissionControlLiveEvents() {
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);
  const wsUrl = useMemo(() => missionControlEventsWsUrl(), []);
  const [conn, setConn] = useState<MissionWsConnectionState>("connecting");

  useEffect(() => {
    const dispose = connectReconnectingMissionWs(wsUrl, {
      onState: setConn,
      onMessage: (raw) => {
        try {
          const event = JSON.parse(raw) as Record<string, unknown>;
          setEvents((prev) => [...prev, event].slice(-500));
        } catch {
          /* ignore non-JSON */
        }
      },
    });
    return dispose;
  }, [wsUrl]);

  const label =
    conn === "open"
      ? "Live"
      : conn === "reconnecting"
        ? "Reconnecting…"
        : conn === "error"
          ? "Connection error (retrying)"
          : "Connecting…";

  return (
    <section className="border-b border-zinc-800 bg-zinc-950/80 px-4 py-3">
      <h2 className="text-sm font-medium text-zinc-200">Live execution</h2>
      <p className="truncate text-xs text-zinc-500" title={wsUrl}>
        {wsUrl} · {label} · {events.length} events
      </p>
      <div className="mt-2 max-h-52 overflow-auto rounded border border-zinc-800 bg-black/40 font-mono text-[11px] leading-snug text-zinc-300">
        {events.length === 0 && conn !== "open" && (
          <div className="border-b border-zinc-900 px-2 py-2 text-zinc-500">
            {conn === "connecting" ? "Connecting to event stream…" : "Waiting for events…"}
          </div>
        )}
        {events.map((e, i) => (
          <pre key={i} className="whitespace-pre-wrap border-b border-zinc-900 px-2 py-1.5 last:border-b-0">
            {JSON.stringify(e, null, 2)}
          </pre>
        ))}
      </div>
    </section>
  );
}
