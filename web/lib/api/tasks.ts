import type { OverviewChecklistTask, OverviewMissionTask, Task as BoardTask } from "@/types/mission-control";

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
  if (s === "snoozed") return "pending";
  return "pending";
}

export function taskReadToBoardTask(row: TaskRead): BoardTask {
  return {
    id: String(row.id),
    title: row.title,
    description: row.description ?? undefined,
    status: mapChecklistStatus(row.status),
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

/** GET /api/v1/tasks — checklist tasks as Kanban-capable models (M4). */
export async function fetchTasksForKanban(): Promise<BoardTask[]> {
  try {
    const rows = await apiFetch<TaskRead[]>("/tasks");
    if (!Array.isArray(rows)) return [];
    return rows.map(taskReadToBoardTask);
  } catch {
    return [];
  }
}

export type TaskPatchPayload = {
  title?: string;
  description?: string | null;
  status?: string;
  category?: string | null;
  priority_score?: number;
};

/** PATCH /api/v1/tasks/{id} */
export async function patchTask(taskId: string, payload: TaskPatchPayload): Promise<BoardTask> {
  const row = await apiFetch<TaskRead>(`/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return taskReadToBoardTask(row);
}

/** POST /api/v1/tasks */
export async function createTask(payload: {
  title: string;
  description?: string | null;
  category?: string;
  priority_score?: number;
}): Promise<BoardTask> {
  const row = await apiFetch<TaskRead>("/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return taskReadToBoardTask(row);
}

/** DELETE /api/v1/tasks/{id} */
export async function deleteTaskById(taskId: string): Promise<void> {
  await apiFetch<null>(`/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
}

/** Map checklist column drop target to a persisted task status. */
export function kanbanColumnToTaskStatus(column: BoardTask["status"] | string): string {
  const c = String(column);
  if (c === "in_progress") return "in_progress";
  if (c === "done") return "done";
  return "pending";
}

export async function updateTaskStatus(taskId: string, newStatus: string): Promise<BoardTask> {
  return patchTask(taskId, { status: kanbanColumnToTaskStatus(newStatus) });
}

/** GET /api/v1/tasks — personal checklist tasks. */
export async function fetchChecklistTasks(): Promise<OverviewChecklistTask[]> {
  try {
    const rows = await apiFetch<TaskRead[]>("/tasks");
    if (!Array.isArray(rows)) return [];
    return rows.map((t) => {
      const bt = taskReadToBoardTask(t);
      return {
        id: bt.id,
        title: bt.title,
        description: bt.description ?? null,
        status: bt.status,
        created_at: bt.created_at,
        updated_at: bt.updated_at,
      };
    });
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
