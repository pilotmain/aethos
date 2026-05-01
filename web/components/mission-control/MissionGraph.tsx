"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useReducer, useState } from "react";
import { AgentCard } from "@/components/mission-control/AgentCard";
import {
  getMissionGraph,
  getMissionState,
  refreshMissionControlStore,
  subscribeMissionStore,
} from "@/lib/state/missionControlStore";
import {
  ensureMissionControlStream,
  subscribeMissionConnection,
  type MissionStreamConnState,
} from "@/lib/ws/missionControlStream";

type GraphNode = {
  id: string;
  label: string;
  status: string;
  handle?: string;
  mission_id?: string;
};

type GraphEdge = { from: string; to: string };

type MissionGraphPayload = { nodes: GraphNode[]; edges: GraphEdge[] };

/** Nodes upstream of currently running agents (execution path). */
function ancestorNodes(edges: GraphEdge[], seeds: Set<string>): Set<string> {
  const incoming = new Map<string, string[]>();
  for (const e of edges) {
    if (!incoming.has(e.to)) incoming.set(e.to, []);
    incoming.get(e.to)!.push(e.from);
  }
  const out = new Set<string>();
  const stack = Array.from(seeds);
  while (stack.length) {
    const id = stack.pop()!;
    if (out.has(id)) continue;
    out.add(id);
    for (const from of incoming.get(id) ?? []) {
      if (!out.has(from)) stack.push(from);
    }
  }
  return out;
}

type TaskRow = {
  mission_id?: string;
  agent_handle?: string;
  output?: unknown;
  status?: string;
};

function formatTaskOutput(output: unknown): string {
  if (output == null) return "";
  if (typeof output === "string") return output;
  try {
    return JSON.stringify(output);
  } catch {
    return String(output);
  }
}

function deriveTasks(st: Record<string, unknown> | null): {
  outputs: Record<string, string>;
  running: Set<string>;
} {
  const outputs: Record<string, string> = {};
  const running = new Set<string>();
  const tasks = Array.isArray(st?.tasks) ? (st.tasks as TaskRow[]) : [];
  for (const t of tasks) {
    const mid = String(t.mission_id || "").trim();
    const h = String(t.agent_handle || "").trim();
    if (!mid || !h) continue;
    const id = `${mid}:${h}`;
    outputs[id] = formatTaskOutput(t.output);
    if (String(t.status || "").toLowerCase() === "running") running.add(id);
  }
  return { outputs, running };
}

/**
 * Agent graph — reads shared Mission Control store (Phase 14 single-stream architecture).
 */
export function MissionGraph() {
  const [, bump] = useReducer((x: number) => x + 1, 0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conn, setConn] = useState<MissionStreamConnState>("connecting");

  useEffect(() => {
    ensureMissionControlStream();
    return subscribeMissionConnection(setConn);
  }, []);

  useEffect(() => {
    return subscribeMissionStore(bump);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      await refreshMissionControlStore();
      setError(null);
    } catch {
      setError("Could not load mission graph");
    } finally {
      setLoading(false);
    }
  }, []);

  const raw = getMissionGraph();
  const graph: MissionGraphPayload = raw
    ? {
        nodes: Array.isArray(raw.nodes) ? (raw.nodes as GraphNode[]) : [],
        edges: Array.isArray(raw.edges) ? (raw.edges as GraphEdge[]) : [],
      }
    : { nodes: [], edges: [] };

  const { outputs, running } = deriveTasks(getMissionState());

  const pathNodes = ancestorNodes(graph.edges, running);

  const live = conn === "open";

  return (
    <section className="flex h-full min-h-[320px] flex-col rounded-xl border border-zinc-800 bg-zinc-950/70 px-4 py-4 transition-colors duration-300">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-medium text-zinc-200">Agent graph</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Tasks and dependencies for your missions.
            {!live && (
              <span className="ml-2 text-zinc-600">
                · Events: {conn === "reconnecting" ? "reconnecting…" : conn}
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

      <div className="mt-4 flex flex-wrap gap-3 transition-all duration-300 ease-out">
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
            active={running.has(n.id)}
            pathHighlight={pathNodes.has(n.id) && !running.has(n.id)}
          />
        ))}
      </div>

      {graph.edges.length > 0 ? (
        <div className="mt-4 rounded-lg border border-zinc-800 bg-black/25 p-3 font-mono text-[11px] text-zinc-400 transition-opacity duration-300">
          <div className="mb-2 text-zinc-500">Dependencies</div>
          <ul className="space-y-1">
            {graph.edges.map((e, i) => {
              const onPath = pathNodes.has(e.from) && pathNodes.has(e.to);
              return (
                <li
                  key={`${e.from}-${e.to}-${i}`}
                  className={`transition-colors duration-300 ${onPath ? "text-emerald-300/90" : ""}`}
                >
                  {e.from} <span className="text-zinc-600">→</span> {e.to}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
