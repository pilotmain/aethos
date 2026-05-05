"use client";

import { AlertCircle, CheckCircle, Clock, Loader2 } from "lucide-react";

import type { OverviewChecklistTask, OverviewMissionTask } from "@/types/mission-control";

export type RecentTasksProps = {
  checklist: OverviewChecklistTask[];
  mission: OverviewMissionTask[];
};

const statusIcon = {
  done: <CheckCircle className="h-4 w-4 text-emerald-500" aria-hidden />,
  in_progress: <Loader2 className="h-4 w-4 animate-spin text-sky-400" aria-hidden />,
  pending: <Clock className="h-4 w-4 text-amber-400" aria-hidden />,
  blocked: <AlertCircle className="h-4 w-4 text-red-400" aria-hidden />,
};

export function RecentTasks({ checklist, mission }: RecentTasksProps) {
  const useMission = checklist.length === 0 && mission.length > 0;
  const rows = useMission ? mission.slice(0, 8) : checklist.slice(0, 8);

  if (rows.length === 0) {
    return <p className="text-sm text-zinc-500">No recent tasks — create checklist items or mission work.</p>;
  }

  return (
    <div className="space-y-3">
      {useMission && (
        <p className="text-xs text-zinc-500">Showing mission tasks (no checklist items yet).</p>
      )}
      {useMission
        ? (rows as OverviewMissionTask[]).map((task) => (
            <div key={task.id} className="flex items-start gap-3 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
              {statusIcon[task.status]}
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-sm font-medium leading-snug text-zinc-100">{task.title}</p>
                {task.agent_handle ? (
                  <p className="text-xs text-zinc-500">Agent: {task.agent_handle}</p>
                ) : null}
                {task.updated_at ? (
                  <p className="text-xs text-zinc-600">Updated: {new Date(task.updated_at).toLocaleString()}</p>
                ) : null}
              </div>
            </div>
          ))
        : (rows as OverviewChecklistTask[]).map((task) => (
            <div key={task.id} className="flex items-start gap-3 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
              {statusIcon[task.status]}
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-sm font-medium leading-snug text-zinc-100">{task.title}</p>
                {task.assigned_to_name ? (
                  <p className="text-xs text-zinc-500">Assigned: {task.assigned_to_name}</p>
                ) : null}
                <p className="text-xs text-zinc-600">Updated: {new Date(task.updated_at).toLocaleString()}</p>
              </div>
            </div>
          ))}
    </div>
  );
}
