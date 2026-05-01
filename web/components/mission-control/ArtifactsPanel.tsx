"use client";

import { ChevronDown, ChevronRight, FileJson, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { webFetch } from "@/lib/api";
import { isConfigured, readConfig } from "@/lib/config";

type ArtifactRow = {
  id: number;
  mission_id: string;
  agent: string;
  artifact: unknown;
  created_at: string | null;
};

type McState = {
  artifacts: ArtifactRow[];
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

export function ArtifactsPanel() {
  const [byAgent, setByAgent] = useState<Record<string, ArtifactRow[]>>({});
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    if (!isConfigured()) {
      setErr("Set API base and user id on the login page to load artifacts.");
      setLoading(false);
      setByAgent({});
      return;
    }
    setErr(null);
    setLoading(true);
    try {
      const uid = readConfig().userId;
      const data = await webFetch<McState>(`/mission-control/state?user_id=${encodeURIComponent(uid)}`);
      const arts = Array.isArray(data.artifacts) ? data.artifacts : [];
      const map: Record<string, ArtifactRow[]> = {};
      for (const a of arts) {
        const key = (a.agent || "unknown").trim() || "unknown";
        if (!map[key]) map[key] = [];
        map[key].push(a);
      }
      setByAgent(map);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setByAgent({});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const agents = Object.keys(byAgent).sort();

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

      {loading && Object.keys(byAgent).length === 0 && !err ? (
        <div className="mt-4 flex items-center gap-2 text-xs text-zinc-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading artifacts…
        </div>
      ) : null}

      {!loading && agents.length === 0 && !err ? (
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
                  {rows.map((row) => (
                    <li
                      key={row.id}
                      title={summarizeArtifact(row.artifact).slice(0, 600)}
                      className="rounded-md border border-zinc-800/60 bg-zinc-950/80 p-2.5 font-mono text-[11px] text-zinc-300 transition-colors duration-200 hover:border-zinc-600 hover:bg-zinc-900/80"
                    >
                      <div className="mb-1 flex flex-wrap items-center gap-2 text-zinc-500">
                        <FileJson className="h-3.5 w-3.5" />
                        <span>mission {(row.mission_id || "?").slice(0, 12)}</span>
                        {row.created_at ? <span>{new Date(row.created_at).toLocaleString()}</span> : null}
                      </div>
                      <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words text-zinc-400">
                        {summarizeArtifact(row.artifact) || "—"}
                      </pre>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-[10px] text-zinc-600">Source: GET /api/v1/mission-control/state (scoped by your user id).</p>
    </section>
  );
}
