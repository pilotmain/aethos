"use client";

import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { DEFAULT_API_BASE, readConfig } from "@/lib/config";

type GraphNode = {
  id: string;
  label: string;
  status: string;
  handle?: string;
  mission_id?: string;
};

type GraphEdge = { from: string; to: string };

type MissionGraphPayload = { nodes: GraphNode[]; edges: GraphEdge[] };

function toWsOrigin(httpBase: string): string {
  try {
    const u = new URL(httpBase.startsWith("http") ? httpBase : `http://${httpBase}`);
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    return u.origin;
  } catch {
    return "ws://127.0.0.1:8010";
  }
}

function graphHttpUrl(): string {
  const c = readConfig();
  const base = (c.apiBase?.trim() || DEFAULT_API_BASE).replace(/\/$/, "");
  return `${base}/api/v1/mission-control/graph`;
}

const STATUS_CLASS: Record<string, string> = {
  queued: "text-zinc-400",
  pending: "text-zinc-400",
  running: "text-orange-400",
  completed: "text-emerald-400",
  failed: "text-red-400",
  blocked: "text-amber-500",
  cancelled: "text-zinc-500",
};

export function MissionGraph() {
  const [graph, setGraph] = useState<MissionGraphPayload>({ nodes: [], edges: [] });
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    fetch(graphHttpUrl())
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status}`);
        return res.json() as Promise<MissionGraphPayload>;
      })
      .then((g) => {
        setGraph({
          nodes: Array.isArray(g.nodes) ? g.nodes : [],
          edges: Array.isArray(g.edges) ? g.edges : [],
        });
        setError(null);
      })
      .catch(() => setError("Could not load mission graph"));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const c = readConfig();
    const base = c.apiBase?.trim() || DEFAULT_API_BASE;
    const wsUrl = `${toWsOrigin(base)}/api/v1/mission-control/events/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = () => {
      refresh();
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
  }, [refresh]);

  return (
    <section className="border-b border-zinc-800 bg-zinc-950/80 px-4 py-4">
      <h2 className="text-sm font-medium text-zinc-200">Mission graph</h2>
      <p className="mt-1 text-xs text-zinc-500">
        Agents and task dependencies (refreshes on live events).
      </p>
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

      <div className="mt-3 flex flex-wrap gap-4">
        {graph.nodes.map((n) => {
          const cls = STATUS_CLASS[n.status] ?? "text-zinc-300";
          const pulse = n.status === "running";
          return (
            <motion.div
              key={n.id}
              layout
              animate={{ scale: pulse ? 1.06 : 1 }}
              transition={{ type: "spring", stiffness: 320, damping: 24 }}
              className={`rounded-md border border-zinc-800 bg-black/30 px-3 py-2 text-sm ${cls}`}
            >
              <div className="font-medium">{n.label}</div>
              <div className="font-mono text-[11px] text-zinc-500">{n.id}</div>
              <div className="text-[11px] uppercase tracking-wide">{n.status}</div>
            </motion.div>
          );
        })}
      </div>

      {graph.edges.length > 0 && (
        <div className="mt-4 rounded border border-zinc-800 bg-black/20 p-3 font-mono text-[11px] text-zinc-400">
          <div className="mb-2 text-zinc-500">Dependencies</div>
          <ul className="space-y-1">
            {graph.edges.map((e, i) => (
              <li key={`${e.from}-${e.to}-${i}`}>
                {e.from} <span className="text-zinc-600">→</span> {e.to}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
