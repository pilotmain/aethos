"use client";

import {
  Pause,
  Play,
  Radio,
  RefreshCw,
  SkipForward,
  Video,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { missionControlEventsWsUrl } from "@/lib/mission-control/eventsWsUrl";
import {
  connectReconnectingMissionWs,
  type MissionWsConnectionState,
} from "@/lib/ws/reconnectingMissionWs";

type ViewMode = "live" | "replay";

/**
 * Live event stream + replay scrubber (Phase 12).
 */
export function MissionControlLiveEvents() {
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);
  const wsUrl = useMemo(() => missionControlEventsWsUrl(), []);
  const [conn, setConn] = useState<MissionWsConnectionState>("connecting");
  const [wsKey, setWsKey] = useState(0);
  const [mode, setMode] = useState<ViewMode>("live");
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const dispose = connectReconnectingMissionWs(wsUrl, {
      onState: setConn,
      onMessage: (raw) => {
        try {
          const event = JSON.parse(raw) as Record<string, unknown>;
          setEvents((prev) => [...prev, event].slice(-800));
        } catch {
          /* ignore non-JSON */
        }
      },
    });
    return dispose;
  }, [wsUrl, wsKey]);

  useEffect(() => {
    if (mode === "live") {
      setCursor(Math.max(0, events.length - 1));
    }
  }, [events, mode]);

  useEffect(() => {
    if (!playing || mode !== "replay") return;
    const id = window.setInterval(() => {
      setCursor((c) => {
        const cap = Math.max(0, events.length - 1);
        if (c >= cap) {
          setPlaying(false);
          return c;
        }
        return c + 1;
      });
    }, 420);
    return () => window.clearInterval(id);
  }, [playing, mode, events.length]);

  const maxIdx = Math.max(0, events.length - 1);
  const displayed =
    mode === "live" ? events : events.slice(0, Math.min(cursor + 1, events.length));

  const connLabel =
    conn === "open"
      ? "Live stream"
      : conn === "reconnecting"
        ? "Reconnecting…"
        : conn === "error"
          ? "Socket error (retrying)"
          : "Connecting…";

  return (
    <section className="flex h-full min-h-[320px] flex-col rounded-xl border border-zinc-800 bg-zinc-950/70">
      <div className="border-b border-zinc-800 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-medium text-zinc-200">Live execution</h2>
            <p className="truncate text-xs text-zinc-500" title={wsUrl}>
              {connLabel} · {events.length} events buffered
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setWsKey((k) => k + 1);
              setPlaying(false);
            }}
            className="inline-flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-[11px] font-medium text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw className="h-3 w-3" />
            Retry connection
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-zinc-800 bg-black/40 p-0.5">
            <button
              type="button"
              onClick={() => {
                setMode("live");
                setPlaying(false);
              }}
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[11px] font-medium ${
                mode === "live" ? "bg-zinc-700 text-white" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <Radio className="h-3 w-3" />
              Live
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("replay");
                setCursor(0);
                setPlaying(false);
              }}
              className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-[11px] font-medium ${
                mode === "replay" ? "bg-zinc-700 text-white" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <Video className="h-3 w-3" />
              Replay
            </button>
          </div>

          {mode === "replay" ? (
            <>
              <button
                type="button"
                onClick={() => setPlaying((p) => !p)}
                disabled={events.length === 0}
                className="inline-flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-[11px] text-zinc-200 hover:bg-zinc-800 disabled:opacity-40"
              >
                {playing ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                {playing ? "Pause" : "Play"}
              </button>
              <button
                type="button"
                onClick={() =>
                  setCursor((c) => Math.min(maxIdx, c + 1))
                }
                disabled={events.length === 0}
                className="inline-flex items-center gap-1 rounded-md border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:bg-zinc-900 disabled:opacity-40"
              >
                <SkipForward className="h-3 w-3" />
                Step
              </button>
              <label className="flex min-w-[140px] flex-1 items-center gap-2 text-[11px] text-zinc-500">
                <span className="shrink-0">Time</span>
                <input
                  type="range"
                  min={0}
                  max={maxIdx}
                  value={Math.min(cursor, maxIdx)}
                  onChange={(e) => {
                    setPlaying(false);
                    setCursor(Number(e.target.value));
                  }}
                  className="h-1 flex-1 accent-violet-500"
                />
                <span className="tabular-nums text-zinc-400">
                  {events.length ? cursor + 1 : 0}/{events.length}
                </span>
              </label>
            </>
          ) : null}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-2">
        <div className="max-h-[min(52vh,520px)] overflow-auto rounded-lg border border-zinc-800/80 bg-black/40 font-mono text-[11px] leading-snug text-zinc-300">
          {displayed.length === 0 && conn !== "open" && (
            <div className="border-b border-zinc-900 px-2 py-3 text-zinc-500">
              {conn === "connecting" ? "Connecting to event stream…" : "Waiting for events…"}
            </div>
          )}
          {displayed.map((e, i) => (
            <pre
              key={`${mode}-${i}-${String((e as { type?: unknown }).type ?? "")}`}
              className={`whitespace-pre-wrap border-b border-zinc-900 px-2 py-1.5 last:border-b-0 ${
                mode === "replay" && i === displayed.length - 1 ? "bg-violet-950/25" : ""
              }`}
            >
              {JSON.stringify(e, null, 2)}
            </pre>
          ))}
        </div>
      </div>
    </section>
  );
}
