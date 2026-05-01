"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { DEFAULT_API_BASE, readConfig } from "@/lib/config";
import { AgentCard } from "@/components/mission-control/AgentCard";
import { missionControlEventsWsUrl } from "@/lib/mission-control/eventsWsUrl";
import { connectReconnectingMissionWs } from "@/lib/ws/reconnectingMissionWs";

type GraphNode = {
  id: string;
  label: string;
  status: string;
  handle?: string;
  mission_id?: string;
};

type GraphEdge = { from: string; to: string };

type MissionGraphPayload = { nodes: GraphNode[]; edges: GraphEdge[] };

type TaskRow = {
  mission_id?: string;
  agent_handle?: string;
  output?: unknown;
};

function graphHttpUrl(): string {
  const c = readConfig();
  const base = (c.apiBase?.trim() || DEFAULT_API_BASE).replace(/\/$/, "");
  const uid = (c.userId || "").trim();
  const q = uid ? `?user_id=${encodeURIComponent(uid)}` : "";
  return `${base}/api/v1/mission-control/graph${q}`;
}

function stateHttpUrl(): string {
  const c = readConfig();
  const base = (c.apiBase?.trim() || DEFAULT_API_BASE).replace(/\/$/, "");
  const uid = (c.userId || "").trim();
  const q = uid ? `?user_id=${encodeURIComponent(uid)}` : "";
  return `${base}/api/v1/mission-control/state${q}`;
}

function formatTaskOutput(output: unknown): string {
  if (output == null) return "";
  if (typeof output === "string") return output;
  try {
    return JSON.stringify(output);
  } catch {
    return String(output);
  }
}

export function MissionGraph() {
  const [graph, setGraph] = useState<MissionGraphPayload>({ nodes: [], edges: [] });
  const [outputs, setOutputs] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [wsStatus, setWsStatus] = useState<string>("connecting");

  const refreshOutputs = useCallback(async () => {
    try {
      const r = await fetch(stateHttpUrl());
      if (!r.ok) return;
      const data = (await r.json()) as { tasks?: TaskRow[] };
      const tasks = Array.isArray(data.tasks) ? data.tasks : [];
      const m: Record<string, string> = {};
      for (const t of tasks) {
        const mid = String(t.mission_id || "").trim();
        const h = String(t.agent_handle || "").trim();
        if (!mid || !h) continue;
        const id = `${mid}:${h}`;
        m[id] = formatTaskOutput(t.output);
      }
      setOutputs(m);
    } catch {
      /* ignore */
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(graphHttpUrl());
      if (!r.ok) throw new Error(`${r.status}`);
      const g = (await r.json()) as MissionGraphPayload;
      setGraph({
        nodes: Array.isArray(g.nodes) ? g.nodes : [],
        edges: Array.isArray(g.edges) ? g.edges : [],
      });
      setError(null);
      await refreshOutputs();
    } catch {
      setError("Could not load mission graph");
    } finally {
      setLoading(false);
    }
  }, [refreshOutputs]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const wsUrl = missionControlEventsWsUrl();
    return connectReconnectingMissionWs(wsUrl, {
      onState: (s) => setWsStatus(s === "open" ? "live" : s),
      onMessage: () => {
        void refresh();
      },
    });
  }, [refresh]);

  return (
    <section className="flex h-full min-h-[320px] flex-col rounded-xl border border-zinc-800 bg-zinc-950/70 px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-medium text-zinc-200">Agent graph</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Tasks and dependencies for your missions.
            {wsStatus !== "live" && (
              <span className="ml-2 text-zinc-600">
                · Events: {wsStatus === "reconnecting" ? "reconnecting…" : wsStatus}
              </span>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-900/80 px-2 py-1 text-[11px] text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Refresh
        </button>
      </div>

      {error ? <p className="mt-2 text-xs text-red-400">{error}</p> : null}

      <div className="mt-4 flex flex-wrap gap-3">
        {loading && graph.nodes.length === 0 ? (
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading graph…
          </div>
        ) : null}
        {graph.nodes.map((n) => (
          <AgentCard
            key={n.id}
            nodeId={n.id}
            label={n.label}
            handle={n.handle}
            status={n.status}
            lastOutput={outputs[n.id] ?? null}
          />
        ))}
      </div>

      {graph.edges.length > 0 ? (
        <div className="mt-4 rounded-lg border border-zinc-800 bg-black/25 p-3 font-mono text-[11px] text-zinc-400">
          <div className="mb-2 text-zinc-500">Dependencies</div>
          <ul className="space-y-1">
            {graph.edges.map((e, i) => (
              <li key={`${e.from}-${e.to}-${i}`}>
                {e.from} <span className="text-zinc-600">→</span> {e.to}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
