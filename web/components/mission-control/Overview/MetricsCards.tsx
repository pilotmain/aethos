"use client";

import { Activity, CreditCard, FolderKanban, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type MetricsCardsProps = {
  projects: { total: number; active: number };
  team: { total: number; active: number };
  budget: { used: number; limit: number; percentage: number };
  health: { api: boolean };
};

export function MetricsCards({ projects, team, budget, health }: MetricsCardsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-zinc-300">Missions</CardTitle>
          <FolderKanban className="h-4 w-4 text-zinc-500" aria-hidden />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tabular-nums text-zinc-50">{projects.active}</div>
          <p className="text-xs text-zinc-500">{projects.total} total in workspace</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-zinc-300">Team roles</CardTitle>
          <Users className="h-4 w-4 text-zinc-500" aria-hidden />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tabular-nums text-zinc-50">{team.total}</div>
          <p className="text-xs text-zinc-500">{team.active} active assignments</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-zinc-300">Token usage</CardTitle>
          <CreditCard className="h-4 w-4 text-zinc-500" aria-hidden />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tabular-nums text-zinc-50">{Math.round(budget.percentage)}%</div>
          <p className="text-xs text-zinc-500">
            {budget.used.toLocaleString()} / {budget.limit.toLocaleString()} (daily cap est.)
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-zinc-300">API</CardTitle>
          <Activity className="h-4 w-4 text-zinc-500" aria-hidden />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{health.api ? "🟢" : "🔴"}</div>
          <p className="text-xs text-zinc-500">{health.api ? "Reachable" : "Unreachable"}</p>
        </CardContent>
      </Card>
    </div>
  );
}
