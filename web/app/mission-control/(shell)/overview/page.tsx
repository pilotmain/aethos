"use client";

import { useCallback, useEffect, useState } from "react";

import { ActivityFeed } from "@/components/mission-control/Overview/ActivityFeed";
import { BudgetGauge } from "@/components/mission-control/Overview/BudgetGauge";
import { MetricsCards } from "@/components/mission-control/Overview/MetricsCards";
import { RecentTasks } from "@/components/mission-control/Overview/RecentTasks";
import { SystemHealth } from "@/components/mission-control/Overview/SystemHealth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMissionControlApiError } from "@/lib/api";
import { fetchBudgetInfo } from "@/lib/api/budget";
import { fetchHealth } from "@/lib/api/health";
import {
  attentionFeedFromState,
  fetchMissionControlState,
  healthFlagsFromState,
  projectMetricsFromState,
} from "@/lib/api/mission-control-state";
import { fetchChecklistTasks, mapMissionTasks, sortTasksByUpdated } from "@/lib/api/tasks";
import { teamMetricsFromState } from "@/lib/api/team";
import type { BudgetInfo, OverviewChecklistTask, OverviewMissionTask, SystemHealthFlags } from "@/types/mission-control";
import Link from "next/link";

function mergeHealth(apiOk: boolean, stateFlags: { cron: boolean; providers: boolean }): SystemHealthFlags {
  return {
    api: apiOk,
    cron: stateFlags.cron,
    providers: stateFlags.providers,
  };
}

export default function MissionControlOverviewPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [budget, setBudget] = useState<BudgetInfo | null>(null);
  const [checklist, setChecklist] = useState<OverviewChecklistTask[]>([]);
  const [missionTasks, setMissionTasks] = useState<OverviewMissionTask[]>([]);
  const [projects, setProjects] = useState({ total: 0, active: 0 });
  const [team, setTeam] = useState({ total: 0, active: 0 });
  const [attention, setAttention] = useState<ReturnType<typeof attentionFeedFromState>>([]);
  const [health, setHealth] = useState<SystemHealthFlags>({ api: false, cron: false, providers: false });
  const [quiet, setQuiet] = useState<boolean | undefined>();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [state, healthRes, tasksRows, budgetInfo] = await Promise.all([
        fetchMissionControlState(48),
        fetchHealth(),
        fetchChecklistTasks(),
        fetchBudgetInfo(),
      ]);

      const hf = healthFlagsFromState(state);
      setHealth(mergeHealth(healthRes.ok, hf));
      setBudget(budgetInfo);
      setProjects(projectMetricsFromState(state));
      setTeam(teamMetricsFromState(state));
      setAttention(attentionFeedFromState(state, 10));
      setQuiet(typeof state?.quiet === "boolean" ? state.quiet : undefined);

      const sorted = [...tasksRows].sort(sortTasksByUpdated);
      setChecklist(sorted);
      setMissionTasks(mapMissionTasks(state?.tasks));

      if (!state && !healthRes.ok) {
        setError("Could not load Mission Control state or API health — check Login → Connection and API URL.");
      }
    } catch (e) {
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-violet-500" />
        <p className="text-sm text-zinc-500">Loading dashboard…</p>
      </div>
    );
  }

  const b =
    budget ??
    ({
      used: 0,
      limit: 100_000,
      remaining: 100_000,
      percentage: 0,
      status: "active",
      blocksToday: 0,
    } satisfies BudgetInfo);

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-50">Overview</h2>
          <p className="mt-1 text-sm text-zinc-400">Live snapshot from Mission Control state and provider usage.</p>
        </div>
        <Link href="/mission-control/legacy" className="text-sm text-violet-400 underline-offset-2 hover:underline">
          Classic console
        </Link>
      </div>

      {error ? (
        <div className="rounded-lg border border-amber-900/60 bg-amber-950/40 px-4 py-3 text-sm text-amber-100">
          {error}
          <button
            type="button"
            className="ml-3 text-violet-400 underline"
            onClick={() => void load()}
          >
            Retry
          </button>
        </div>
      ) : null}

      {quiet === true ? (
        <p className="text-xs text-zinc-500">System reports a quiet window — no blocking attention items.</p>
      ) : null}

      <MetricsCards
        projects={projects}
        team={team}
        budget={{ used: b.used, limit: b.limit, percentage: b.percentage }}
        health={{ api: health.api }}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent tasks</CardTitle>
            <CardDescription>Checklist tasks from `/api/v1/tasks`, or mission tasks if empty.</CardDescription>
          </CardHeader>
          <CardContent>
            <RecentTasks checklist={checklist} mission={missionTasks} />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Budget usage</CardTitle>
              <CardDescription>
                From `/api/v1/providers/usage` vs estimated daily cap ({b.limit.toLocaleString()} tokens).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <BudgetGauge percentage={b.percentage} status={b.status} />
              {b.blocksToday > 0 ? (
                <p className="mt-2 text-xs text-amber-400">Budget blocks today: {b.blocksToday}</p>
              ) : null}
            </CardContent>
          </Card>
          <SystemHealth health={health} />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Attention & activity</CardTitle>
          <CardDescription>Top items from Mission Control `attention` queue.</CardDescription>
        </CardHeader>
        <CardContent>
          <ActivityFeed items={attention} />
        </CardContent>
      </Card>
    </div>
  );
}
