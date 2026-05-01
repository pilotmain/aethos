"use client";

import { motion } from "framer-motion";
import { ChevronDown, ChevronRight, FileJson, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useReducer, useState } from "react";
import { isConfigured } from "@/lib/config";
import {
  getMissionState,
  refreshMissionControlStore,
  subscribeMissionStore,
} from "@/lib/state/missionControlStore";

type ArtifactRow = {
  id: number;
  mission_id: string;
  agent: string;
  artifact: unknown;
  created_at: string | null;
};

type McState = {
  artifacts?: ArtifactRow[];
};

function summarizeArtifact(a: unknown): string {
  if (a == null) return "";
  if (typeof a === "string") return a.slice(0, 400);
  if (typeof a === "object") {
    const o = a as Record<string, unknown>;
    const text = o.text ?? o.content ?? o.body ?? o.summary;
    if (typeof text === "string") return text.slice(0, 400);
    try {
      return JSON.stringify(a).slice(0, 400);
    } catch {
      return String(a).slice(0, 400);
    }
  }
  return String(a).slice(0, 400);
}

function groupByAgent(data: McState | null): Record<string, ArtifactRow[]> {
  const arts = Array.isArray(data?.artifacts) ? data!.artifacts! : [];
  const map: Record<string, ArtifactRow[]> = {};
  for (const a of arts) {
    const key = (a.agent || "unknown").trim() || "unknown";
    if (!map[key]) map[key] = [];
    map[key].push(a);
  }
  return map;
}

export function ArtifactsPanel() {
  const [, bump] = useReducer((x: number) => x + 1, 0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const configured = isConfigured();

  useEffect(() => {
    return subscribeMissionStore(bump);
  }, []);

  const byAgent = groupByAgent(getMissionState() as McState | null);

  const load = useCallback(async () => {
    if (!configured) {
      setErr("Set API base and user id on the login page to load artifacts.");
      return;
    }
    setErr(null);
    setLoading(true);
    try {
      await refreshMissionControlStore();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [configured]);

  const agents = Object.keys(byAgent).sort();
  const configHint =
    !configured && !err
      ? "Set API base and user id on the login page to load artifacts."
      : null;

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950/70 px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-zinc-200">Artifacts</h2>
          <p className="text-xs text-zinc-500">Outputs grouped by agent (from Mission Control state).</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900/80 px-2.5 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Refresh
        </button>
      </div>

      {err ? (
        <p className="mt-3 rounded-md border border-rose-500/30 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">{err}</p>
      ) : null}
      {configHint ? (
        <p className="mt-3 rounded-md border border-amber-500/25 bg-amber-950/30 px-3 py-2 text-xs text-amber-100">
          {configHint}
        </p>
      ) : null}

      {loading && agents.length === 0 && !err ? (
        <div className="mt-4 flex items-center gap-2 text-xs text-zinc-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Refreshing artifacts…
        </div>
      ) : null}

      {!loading && configured && agents.length === 0 && !err ? (
        <p className="mt-4 text-sm text-zinc-500">No artifacts yet. Run a mission to produce outputs.</p>
      ) : null}

      <div className="mt-4 space-y-2">
        {agents.map((agent) => {
          const rows = byAgent[agent] ?? [];
          const open = expanded[agent] ?? false;
          return (
            <div key={agent} className="rounded-lg border border-zinc-800/90 bg-black/25">
              <button
                type="button"
                onClick={() => setExpanded((e) => ({ ...e, [agent]: !open }))}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-zinc-200 hover:bg-zinc-900/50"
              >
                {open ? <ChevronDown className="h-4 w-4 shrink-0 text-zinc-500" /> : (
                  <ChevronRight className="h-4 w-4 shrink-0 text-zinc-500" />
                )}
                <span className="font-mono text-xs text-emerald-400/90">@{agent}</span>
                <span className="text-xs text-zinc-600">({rows.length})</span>
              </button>
              {open ? (
                <ul className="space-y-2 border-t border-zinc-800/80 px-3 pb-3 pt-2">
                  {rows.map((row, ri) => (
                    <motion.li
                      key={row.id}
                      title={summarizeArtifact(row.artifact).slice(0, 600)}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.35, ease: "easeOut", delay: Math.min(ri, 16) * 0.035 }}
                      className="rounded-md border border-zinc-800/60 bg-zinc-950/80 p-2.5 font-mono text-[11px] text-zinc-300 transition-colors duration-300 hover:border-zinc-600 hover:bg-zinc-900/80"
                    >
                      <div className="mb-1 flex flex-wrap items-center gap-2 text-zinc-500">
                        <FileJson className="h-3.5 w-3.5" />
                        <span>mission {(row.mission_id || "?").slice(0, 12)}</span>
                        {row.created_at ? <span>{new Date(row.created_at).toLocaleString()}</span> : null}
                      </div>
                      <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words text-zinc-400">
                        {summarizeArtifact(row.artifact) || "—"}
                      </pre>
                    </motion.li>
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-[10px] text-zinc-600">Source: shared Mission Control store (GET /api/v1/mission-control/state).</p>
    </section>
  );
}
