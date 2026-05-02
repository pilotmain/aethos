"use client";

import { Gauge, Target, Zap } from "lucide-react";

/** Phase 47 — goal tracking, autonomy rate, and efficiency from ``phase46`` snapshot. */
export function ProductionIntelPanel(props: {
  shellLight: boolean;
  phase46?: Record<string, unknown> | null;
  loading?: boolean;
}) {
  const { shellLight, phase46, loading } = props;
  const p46 = phase46 && typeof phase46 === "object" ? phase46 : null;
  const tracking = Array.isArray(p46?.goal_tracking) ? (p46!.goal_tracking as Record<string, unknown>[]) : [];
  const rate = (p46?.autonomy_rate_control as Record<string, unknown> | undefined) ?? undefined;
  const stability = (p46?.autonomy_stability as Record<string, unknown> | undefined) ?? undefined;
  const effTop = (p46?.system_efficiency as Record<string, unknown> | undefined) ?? {};
  const effNested = (effTop.system_efficiency as Record<string, unknown> | undefined) ?? {};
  const suggestions = Array.isArray(effNested.optimization_suggestions)
    ? (effNested.optimization_suggestions as string[])
    : [];

  const cardTitle = shellLight ? "text-zinc-600" : "text-zinc-400";
  const stat = shellLight ? "text-zinc-900" : "text-zinc-50";

  return (
    <section
      className={`rounded-xl border p-4 transition-colors duration-300 ${
        shellLight ? "border-zinc-200 bg-white/90" : "border-zinc-800/80 bg-zinc-950/50"
      }`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className={`text-sm font-semibold ${shellLight ? "text-zinc-900" : "text-zinc-100"}`}>
          Production intelligence
        </h2>
        {loading ? (
          <span className={`text-[10px] ${cardTitle}`}>Loading…</span>
        ) : null}
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <div
          className={`rounded-lg border p-3 ${
            shellLight ? "border-zinc-200 bg-white" : "border-zinc-700/80 bg-zinc-900/40"
          }`}
        >
          <div className={`mb-1 flex items-center gap-2 text-xs font-medium ${cardTitle}`}>
            <Target className="h-4 w-4 shrink-0" aria-hidden />
            Goal tracking
          </div>
          <p className={`text-2xl font-semibold tabular-nums ${stat}`}>{tracking.length}</p>
          <p className={`mt-1 text-[11px] ${cardTitle}`}>Active goals with spawned task links</p>
          {tracking[0] ? (
            <p className={`mt-2 truncate text-[10px] ${cardTitle}`} title={String(tracking[0].title ?? "")}>
              Latest: {String(tracking[0].title ?? "").slice(0, 120)}
              {String(tracking[0].title ?? "").length > 120 ? "…" : ""}
            </p>
          ) : (
            <p className={`mt-2 text-[10px] ${cardTitle}`}>No goal roots yet.</p>
          )}
        </div>

        <div
          className={`rounded-lg border p-3 ${
            shellLight ? "border-zinc-200 bg-white" : "border-zinc-700/80 bg-zinc-900/40"
          }`}
        >
          <div className={`mb-1 flex items-center gap-2 text-xs font-medium ${cardTitle}`}>
            <Zap className="h-4 w-4 shrink-0" aria-hidden />
            Autonomy stability
          </div>
          <p className={`text-2xl font-semibold tabular-nums ${stat}`}>
            {stability?.rate_allowed === false ? "Limited" : "OK"}
          </p>
          <p className={`mt-1 text-[11px] ${cardTitle}`}>
            Pending {String(stability?.pending_tasks ?? "—")} · tokens today{" "}
            {String(stability?.tokens_today ?? "—")}
          </p>
          {rate?.reason ? (
            <p className={`mt-2 text-[10px] text-amber-600 dark:text-amber-300`}>Reason: {String(rate.reason)}</p>
          ) : null}
        </div>

        <div
          className={`rounded-lg border p-3 ${
            shellLight ? "border-zinc-200 bg-white" : "border-zinc-700/80 bg-zinc-900/40"
          }`}
        >
          <div className={`mb-1 flex items-center gap-2 text-xs font-medium ${cardTitle}`}>
            <Gauge className="h-4 w-4 shrink-0" aria-hidden />
            Efficiency
          </div>
          <p className={`text-2xl font-semibold tabular-nums ${stat}`}>
            {typeof effNested.token_waste_ratio === "number" ? effNested.token_waste_ratio : "—"}
          </p>
          <p className={`mt-1 text-[11px] ${cardTitle}`}>Token waste ratio (heuristic)</p>
          {suggestions[0] ? (
            <p className={`mt-2 line-clamp-3 text-[10px] ${cardTitle}`}>{suggestions[0]}</p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
