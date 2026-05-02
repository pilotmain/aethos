"use client";

import { Sparkles } from "lucide-react";
import { useCallback, useState } from "react";
import { formatMissionControlApiError, webFetch } from "@/lib/api";
import { isConfigured } from "@/lib/config";

type AutonomousTaskRow = {
  id: string;
  title?: string;
  state?: string;
  priority?: number;
  auto_generated?: boolean;
  origin?: string;
};

type DecisionRow = { id: string; summary?: string };
type FeedbackRow = {
  id: string;
  task_id?: string;
  outcome?: string;
  reason?: string;
  iterations?: unknown;
  cost_usd?: unknown;
  success?: unknown;
};

type AutonomyStats = {
  execution_attempts?: number;
  execution_successes?: number;
  success_rate?: number | null;
};

/** Phase 44–45 — autonomous queue, decisions, feedback, and execution stats from MC state. */
export function AutonomyIntelligencePanel(props: {
  shellLight: boolean;
  autonomousTasks?: AutonomousTaskRow[];
  autonomyDecisions?: DecisionRow[];
  autonomyFeedback?: FeedbackRow[];
  autonomyExecutionStats?: AutonomyStats;
  loading?: boolean;
  onRefresh?: () => void;
}) {
  const {
    shellLight,
    autonomousTasks,
    autonomyDecisions,
    autonomyFeedback,
    autonomyExecutionStats,
    loading,
    onRefresh,
  } = props;
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const interrupt = useCallback(
    async (id: string) => {
      if (!isConfigured()) return;
      setErr(null);
      setBusy(id);
      try {
        await webFetch(`/mission-control/autonomy/tasks/${encodeURIComponent(id)}/interrupt`, {
          method: "POST",
        });
        onRefresh?.();
      } catch (e) {
        setErr(formatMissionControlApiError(e));
      } finally {
        setBusy(null);
      }
    },
    [onRefresh],
  );

  if (!isConfigured()) return null;

  const cardTitle = shellLight ? "text-zinc-600" : "text-zinc-400";
  const border = shellLight ? "border-zinc-200 bg-white/90" : "border-zinc-800/80 bg-zinc-950/50";
  const btn = shellLight
    ? "border-zinc-300 text-zinc-800 hover:bg-zinc-100"
    : "border-zinc-600 text-zinc-200 hover:bg-zinc-800";

  const tasks = Array.isArray(autonomousTasks) ? autonomousTasks : [];
  const decisions = Array.isArray(autonomyDecisions) ? autonomyDecisions : [];
  const feedback = Array.isArray(autonomyFeedback) ? autonomyFeedback : [];

  return (
    <section className={`rounded-xl border p-4 transition-colors duration-300 ${border}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className={`flex items-center gap-2 text-sm font-semibold ${shellLight ? "text-zinc-900" : "text-zinc-100"}`}>
          <Sparkles className="h-4 w-4 shrink-0 text-amber-400" aria-hidden />
          Autonomy intelligence
        </h2>
        {loading ? (
          <span className={`text-xs ${cardTitle}`}>Loading…</span>
        ) : null}
      </div>
      {err ? <p className={`mb-2 text-xs ${shellLight ? "text-rose-700" : "text-rose-300"}`}>{err}</p> : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <div>
          <p className={`mb-2 text-xs font-medium ${cardTitle}`}>Autonomous tasks ({tasks.length})</p>
          <ul className="max-h-52 space-y-2 overflow-y-auto text-xs">
            {tasks.length === 0 ? (
              <li className={shellLight ? "text-zinc-500" : "text-zinc-500"}>None queued.</li>
            ) : (
              tasks.map((t) => (
                <li
                  key={t.id}
                  className={`rounded-md border p-2 ${shellLight ? "border-zinc-200 bg-zinc-50" : "border-zinc-700 bg-zinc-900/40"}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className={`font-medium ${shellLight ? "text-zinc-900" : "text-zinc-100"}`}>
                        {(t.title || "").slice(0, 200)}
                      </p>
                      <p className={`mt-1 ${cardTitle}`}>
                        state={t.state ?? "—"} · pri={t.priority ?? "—"} · {t.origin ?? "—"}
                        {(t as { executing?: boolean }).executing ? " · executing" : ""}
                      </p>
                      {(t as { last_reply_preview?: string }).last_reply_preview ? (
                        <p className={`mt-1 line-clamp-2 ${cardTitle}`}>
                          {(t as { last_reply_preview?: string }).last_reply_preview}
                        </p>
                      ) : null}
                    </div>
                    {t.state === "pending" ? (
                      <button
                        type="button"
                        className={`shrink-0 rounded border px-2 py-0.5 text-[11px] ${btn}`}
                        disabled={busy === t.id}
                        onClick={() => void interrupt(t.id)}
                      >
                        {busy === t.id ? "…" : "Interrupt"}
                      </button>
                    ) : null}
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
        <div>
          <p className={`mb-2 text-xs font-medium ${cardTitle}`}>Decision logs ({decisions.length})</p>
          <ul className="max-h-52 space-y-2 overflow-y-auto text-xs">
            {decisions.length === 0 ? (
              <li className={shellLight ? "text-zinc-500" : "text-zinc-500"}>No cycles yet.</li>
            ) : (
              decisions.map((d) => (
                <li
                  key={d.id}
                  className={`rounded-md border p-2 ${shellLight ? "border-zinc-200 bg-zinc-50" : "border-zinc-700 bg-zinc-900/40"}`}
                >
                  {(d.summary || "").slice(0, 400)}
                </li>
              ))
            )}
          </ul>
        </div>
        <div>
          <p className={`mb-2 text-xs font-medium ${cardTitle}`}>Feedback ({feedback.length})</p>
          <ul className="max-h-52 space-y-2 overflow-y-auto text-xs">
            {feedback.length === 0 ? (
              <li className={shellLight ? "text-zinc-500" : "text-zinc-500"}>No outcomes logged.</li>
            ) : (
              feedback.map((f) => (
                <li
                  key={f.id}
                  className={`rounded-md border p-2 ${shellLight ? "border-zinc-200 bg-zinc-50" : "border-zinc-700 bg-zinc-900/40"}`}
                >
                  <span className="font-mono text-[10px]">{f.task_id}</span>
                  <span className={`ml-2 ${cardTitle}`}>{f.outcome}</span>
                  <p className={`mt-1 ${cardTitle}`}>{(f.reason || "").slice(0, 240)}</p>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>
    </section>
  );
}
