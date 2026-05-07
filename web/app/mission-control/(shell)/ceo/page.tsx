"use client";

import { useCallback, useEffect, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMissionControlApiError, webFetch } from "@/lib/api";

type CeoSummary = {
  total_agents: number;
  active_agents: number;
  busy_agents: number;
  paused_agents: number;
  total_actions_today: number;
  overall_success_rate: number;
};

type CeoAgentRow = {
  id?: string;
  name?: string;
  domain?: string;
  status?: string;
  total_actions?: number;
  success_rate?: number;
};

export default function CEODashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<CeoSummary | null>(null);
  const [agents, setAgents] = useState<CeoAgentRow[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await webFetch<{ ok?: boolean; summary?: CeoSummary; agents?: CeoAgentRow[] }>(
        "/ceo/dashboard",
      );
      if (res.summary) {
        setSummary(res.summary);
      } else {
        setSummary(null);
      }
      setAgents(Array.isArray(res.agents) ? res.agents : []);
    } catch (e) {
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
      setSummary(null);
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">CEO Dashboard</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Orchestration agent oversight and performance (same registry as API{" "}
          <code className="rounded bg-zinc-900 px-1.5 py-0.5 text-xs text-zinc-300">/api/v1/agents</code>
          ).
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : error ? (
        <Card className="border-red-900/50 bg-red-950/20">
          <CardHeader>
            <CardTitle className="text-red-200">Could not load dashboard</CardTitle>
            <CardDescription className="text-red-300/90">{error}</CardDescription>
          </CardHeader>
        </Card>
      ) : summary ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card className="border-zinc-800 bg-zinc-900/40">
            <CardHeader className="pb-2">
              <CardDescription className="text-zinc-400">Agents</CardDescription>
              <CardTitle className="text-3xl font-semibold text-zinc-100">{summary.total_agents}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-zinc-500">
              Idle {summary.active_agents} · Busy {summary.busy_agents} · Paused {summary.paused_agents}
            </CardContent>
          </Card>
          <Card className="border-zinc-800 bg-zinc-900/40">
            <CardHeader className="pb-2">
              <CardDescription className="text-zinc-400">Actions today</CardDescription>
              <CardTitle className="text-3xl font-semibold text-zinc-100">
                {summary.total_actions_today}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-zinc-500">Activity tracker (rolling window)</CardContent>
          </Card>
          <Card className="border-zinc-800 bg-zinc-900/40 sm:col-span-2 lg:col-span-1">
            <CardHeader className="pb-2">
              <CardDescription className="text-zinc-400">Overall success rate</CardDescription>
              <CardTitle className="text-3xl font-semibold text-zinc-100">
                {summary.overall_success_rate}%
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-zinc-500">Weighted by recent actions</CardContent>
          </Card>
        </div>
      ) : (
        <Card className="border-zinc-800 bg-zinc-900/40">
          <CardContent className="py-8 text-center text-sm text-zinc-400">
            No summary returned. Enable orchestration and create agents from Mission Control or the API.
          </CardContent>
        </Card>
      )}

      {agents.length > 0 ? (
        <Card className="border-zinc-800 bg-zinc-900/40">
          <CardHeader>
            <CardTitle className="text-zinc-100">Agent roster</CardTitle>
            <CardDescription className="text-zinc-400">
              From <code className="rounded bg-zinc-950 px-1 text-[11px]">GET /api/v1/ceo/dashboard</code> (
              same registry as <code className="rounded bg-zinc-950 px-1 text-[11px]">/agents/list</code>).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {agents.map((a) => (
              <div
                key={String(a.id ?? a.name)}
                className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/80 py-2 last:border-0"
              >
                <div className="min-w-0">
                  <span className="font-medium text-zinc-100">@{String(a.name ?? "agent")}</span>
                  <span className="ml-2 rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400">
                    {String(a.domain ?? "general")}
                  </span>
                </div>
                <div className="flex shrink-0 items-center gap-3 text-xs text-zinc-500">
                  {typeof a.total_actions === "number" ? <span>{a.total_actions} actions</span> : null}
                  {typeof a.success_rate === "number" ? (
                    <span>{Math.round(a.success_rate)}% success</span>
                  ) : null}
                  <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-300">
                    {String(a.status ?? "idle")}
                  </span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-zinc-800 bg-zinc-900/40">
        <CardHeader>
          <CardTitle className="text-zinc-100">Roadmap</CardTitle>
          <CardDescription className="text-zinc-400">
            Deeper CEO controls (interventions, redirects, feed) will plug into{" "}
            <code className="rounded bg-zinc-950 px-1.5 py-0.5 text-xs">/api/v1/ceo/*</code>.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
