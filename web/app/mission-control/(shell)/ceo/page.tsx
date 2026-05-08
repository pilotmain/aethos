"use client";

import { useCallback, useEffect, useState } from "react";

import { formatMissionControlApiError, webFetch } from "@/lib/api";

type CeoSummary = {
  total_agents: number;
  active_agents: number;
  busy_agents: number;
  paused_agents: number;
  total_actions_today: number;
  overall_success_rate: number;
  total_cost_today_usd?: number;
  total_llm_calls_today?: number;
};

type CeoAgentRow = {
  id?: string;
  name?: string;
  domain?: string;
  status?: string;
  total_actions?: number;
  success_rate?: number;
};

type CeoCostByProvider = {
  provider?: string;
  calls?: number;
  total_tokens?: number;
  estimated_cost_usd?: number;
};

type CeoCostToday = {
  total_cost_usd: number;
  system_key_cost_usd?: number;
  user_key_cost_usd?: number;
  total_calls: number;
  total_tokens: number;
  by_provider?: CeoCostByProvider[];
  scope?: "owner" | "user";
};

function formatUsd(value: number | null | undefined): string {
  const v = typeof value === "number" && Number.isFinite(value) ? value : 0;
  if (v < 0.01 && v > 0) return `<$0.01`;
  return `$${v.toFixed(2)}`;
}

function formatTokens(value: number | null | undefined): string {
  const v = typeof value === "number" && Number.isFinite(value) ? value : 0;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
  return String(v);
}

function summaryFromAgents(rows: CeoAgentRow[]): CeoSummary {
  const idle = rows.filter((a) => (a.status || "").toLowerCase() === "idle").length;
  const busy = rows.filter((a) => (a.status || "").toLowerCase() === "busy").length;
  const paused = rows.filter((a) => (a.status || "").toLowerCase() === "paused").length;
  const actions = rows.reduce((s, a) => s + (typeof a.total_actions === "number" ? a.total_actions : 0), 0);
  const withRate = rows.filter((a) => typeof a.success_rate === "number");
  const avg =
    withRate.length > 0 ? withRate.reduce((s, a) => s + (a.success_rate as number), 0) / withRate.length : 100;
  return {
    total_agents: rows.length,
    active_agents: idle,
    busy_agents: busy,
    paused_agents: paused,
    total_actions_today: actions,
    overall_success_rate: Math.round(avg),
  };
}

async function loadCeoState(): Promise<{
  summary: CeoSummary;
  agents: CeoAgentRow[];
  costToday: CeoCostToday | null;
}> {
  try {
    const res = await webFetch<{
      ok?: boolean;
      summary?: CeoSummary;
      agents?: CeoAgentRow[];
      cost_today?: CeoCostToday;
    }>("/ceo/dashboard");
    const agents = Array.isArray(res?.agents) ? res.agents : [];
    const summary = res?.summary ?? summaryFromAgents(agents);
    return { summary, agents, costToday: res?.cost_today ?? null };
  } catch {
    /* Falls back to /agents/list (keeps page useful when ceo dashboard is gated). */
    const fallback = await webFetch<{ agents?: CeoAgentRow[] }>("/agents/list");
    const agents = Array.isArray(fallback?.agents) ? fallback.agents : [];
    return { summary: summaryFromAgents(agents), agents, costToday: null };
  }
}

export default function CEODashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<CeoSummary | null>(null);
  const [agents, setAgents] = useState<CeoAgentRow[]>([]);
  const [costToday, setCostToday] = useState<CeoCostToday | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { summary: s, agents: a, costToday: c } = await loadCeoState();
      setSummary(s);
      setAgents(a);
      setCostToday(c);
    } catch (e) {
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
      setSummary(null);
      setAgents([]);
      setCostToday(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-violet-500 border-t-transparent" />
          <p className="mt-2 text-sm text-zinc-500">Loading agents…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <p className="text-rose-300">Could not load dashboard: {error}</p>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
        >
          Retry
        </button>
      </div>
    );
  }

  const totalAgents = summary?.total_agents ?? agents.length;
  const idleAgents = summary?.active_agents ?? 0;
  const busyAgents = summary?.busy_agents ?? Math.max(0, totalAgents - idleAgents);
  const successRate = summary?.overall_success_rate ?? 100;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-50">CEO Dashboard</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Orchestration agent oversight and performance (same registry as API{" "}
          <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs text-zinc-300">/api/v1/ceo/dashboard</code>
          ).
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="text-2xl font-bold text-zinc-100">{totalAgents}</div>
          <p className="text-sm text-zinc-400">Total agents</p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="text-2xl font-bold text-emerald-400">{idleAgents}</div>
          <p className="text-sm text-zinc-400">Idle</p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="text-2xl font-bold text-amber-400">{busyAgents}</div>
          <p className="text-sm text-zinc-400">Busy</p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="text-2xl font-bold text-zinc-100">{successRate}%</div>
          <p className="text-sm text-zinc-400">Success rate</p>
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 p-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Today's LLM cost</h2>
            <p className="text-xs text-zinc-500">
              From <code className="rounded bg-zinc-950 px-1 text-[11px]">llm_usage_events</code> ·
              cost-aware routing logs each call's chosen model and estimated USD.
              {costToday?.scope === "user" ? " (Scoped to your user.)" : null}
            </p>
          </div>
          {summary?.total_cost_today_usd !== undefined ? (
            <div className="text-right">
              <div className="text-2xl font-bold text-zinc-100">
                {formatUsd(summary.total_cost_today_usd)}
              </div>
              <p className="text-xs text-zinc-500">
                {summary.total_llm_calls_today ?? 0} call(s) ·{" "}
                {formatTokens(costToday?.total_tokens)} tokens
              </p>
            </div>
          ) : null}
        </div>
        {costToday && costToday.total_calls > 0 ? (
          <div className="grid gap-px bg-zinc-900/60 sm:grid-cols-3">
            <div className="bg-zinc-950/60 p-4">
              <div className="text-lg font-semibold text-zinc-100">
                {formatUsd(costToday.system_key_cost_usd)}
              </div>
              <p className="text-xs text-zinc-500">System keys</p>
            </div>
            <div className="bg-zinc-950/60 p-4">
              <div className="text-lg font-semibold text-zinc-100">
                {formatUsd(costToday.user_key_cost_usd)}
              </div>
              <p className="text-xs text-zinc-500">BYOK (user keys)</p>
            </div>
            <div className="bg-zinc-950/60 p-4">
              <div className="text-sm text-zinc-300">
                {(costToday.by_provider || []).slice(0, 3).map((p) => (
                  <div
                    key={String(p.provider ?? "?")}
                    className="flex items-center justify-between gap-2"
                  >
                    <span className="text-zinc-400">{String(p.provider ?? "?")}</span>
                    <span className="text-zinc-200">
                      {formatUsd(p.estimated_cost_usd)} · {p.calls ?? 0}
                    </span>
                  </div>
                ))}
                {(costToday.by_provider || []).length === 0 ? (
                  <p className="text-xs text-zinc-500">No provider breakdown.</p>
                ) : null}
              </div>
              <p className="mt-1 text-xs text-zinc-500">By provider (cost · calls)</p>
            </div>
          </div>
        ) : (
          <div className="p-4 text-sm text-zinc-500">
            No LLM calls recorded today yet.
          </div>
        )}
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40">
        <div className="border-b border-zinc-800 p-4">
          <h2 className="text-lg font-semibold text-zinc-100">Agent roster</h2>
          <p className="text-xs text-zinc-500">
            From <code className="rounded bg-zinc-950 px-1 text-[11px]">GET /api/v1/ceo/dashboard</code> (
            same registry as <code className="rounded bg-zinc-950 px-1 text-[11px]">/agents/list</code>).
          </p>
        </div>
        <div className="divide-y divide-zinc-800">
          {agents.map((agent) => (
            <div
              key={String(agent.id ?? agent.name ?? Math.random())}
              className="flex items-center justify-between gap-4 p-4"
            >
              <div className="min-w-0">
                <div className="font-medium text-zinc-100">@{String(agent.name ?? "agent")}</div>
                <div className="text-sm text-zinc-500">Domain: {String(agent.domain ?? "general")}</div>
              </div>
              <div className="shrink-0 text-right text-sm text-zinc-400">
                <div>
                  Status: <span className="text-zinc-200">{String(agent.status ?? "idle")}</span>
                </div>
                <div>
                  Success: {typeof agent.success_rate === "number" ? Math.round(agent.success_rate) : 100}% (
                  {typeof agent.total_actions === "number" ? agent.total_actions : 0} actions)
                </div>
              </div>
            </div>
          ))}
          {agents.length === 0 ? (
            <div className="p-8 text-center text-sm text-zinc-500">
              No agents found. Create one from Mission Control or the API.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
