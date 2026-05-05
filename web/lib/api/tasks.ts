import type { OverviewChecklistTask, OverviewMissionTask } from "@/types/mission-control";

import { apiFetch } from "@/lib/api/client";

type TaskRead = {
  id: number;
  title: string;
  description?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

function mapChecklistStatus(raw: string): OverviewChecklistTask["status"] {
  const s = (raw || "").toLowerCase();
  if (s === "completed" || s === "done") return "done";
  if (s === "in_progress" || s === "doing" || s === "active") return "in_progress";
  if (s === "blocked") return "blocked";
  return "pending";
}

/** GET /api/v1/tasks — personal checklist tasks. */
export async function fetchChecklistTasks(): Promise<OverviewChecklistTask[]> {
  try {
    const rows = await apiFetch<TaskRead[]>("/tasks");
    if (!Array.isArray(rows)) return [];
    return rows.map((t) => ({
      id: String(t.id),
      title: t.title,
      description: t.description,
      status: mapChecklistStatus(t.status),
      created_at: t.created_at,
      updated_at: t.updated_at,
    }));
  } catch {
    return [];
  }
}

export function sortTasksByUpdated(a: { updated_at: string }, b: { updated_at: string }): number {
  return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
}

export function mapMissionTasks(raw: unknown): OverviewMissionTask[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((t) => {
      if (!t || typeof t !== "object") return null;
      const o = t as Record<string, unknown>;
      const id = String(o.id ?? "");
      const taskText = String(o.task ?? o.title ?? "Mission task");
      const st = String(o.status ?? "pending").toLowerCase();
      let status: OverviewMissionTask["status"] = "pending";
      if (st === "completed" || st === "done") status = "done";
      else if (st === "running" || st === "in_progress") status = "in_progress";
      else if (st === "failed" || st === "blocked") status = "blocked";
      return {
        id,
        mission_id: o.mission_id != null ? String(o.mission_id) : undefined,
        title: taskText,
        status,
        agent_handle: o.agent_handle != null ? String(o.agent_handle) : undefined,
        updated_at: o.started_at != null ? String(o.started_at) : undefined,
      } satisfies OverviewMissionTask;
    })
    .filter(Boolean) as OverviewMissionTask[];
}
