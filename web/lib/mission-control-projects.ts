import type { MissionControlStatePayload } from "@/lib/api/mission-control-state";
import type { WorkspaceProjectOut } from "@/lib/api/projects";
import type { Project, Task } from "@/types/mission-control";

import { mapMissionTasks } from "@/lib/api/tasks";

export const CHECKLIST_PROJECT_ID = "checklist";

export function workspaceProjectRouteId(id: number): string {
  return `ws-${id}`;
}

export function missionProjectRouteId(missionId: string | number): string {
  return `mission-${missionId}`;
}

export type ParsedProjectsRoute =
  | { mode: "checklist" }
  | { mode: "workspace"; wsId: number }
  | { mode: "mission"; missionId: string };

export function parseProjectsRouteSegment(segment: string): ParsedProjectsRoute | null {
  if (segment === CHECKLIST_PROJECT_ID) return { mode: "checklist" };
  if (segment.startsWith("ws-")) {
    const n = Number(segment.slice(3));
    if (!Number.isFinite(n)) return null;
    return { mode: "workspace", wsId: n };
  }
  if (segment.startsWith("mission-")) {
    const id = segment.slice("mission-".length);
    if (!id) return null;
    return { mode: "mission", missionId: id };
  }
  return null;
}

export function taskProgressPercent(tasks: { status: Task["status"] }[]): number {
  if (!tasks.length) return 0;
  const done = tasks.filter((t) => t.status === "done").length;
  return Math.round((done / tasks.length) * 100);
}

function missionCardStatus(raw: string): Project["status"] {
  const s = (raw || "").toLowerCase();
  if (s === "completed") return "completed";
  if (s === "paused" || s === "cancelled") return "paused";
  if (s === "failed") return "archived";
  return "active";
}

export function missionTasksForMissionId(rawTasks: unknown, missionId: string): Task[] {
  const mapped = mapMissionTasks(rawTasks).filter((t) => String(t.mission_id ?? "") === missionId);
  return mapped.map((t) => ({
    id: String(t.id),
    title: t.title,
    status: t.status,
    assigned_to_name: t.agent_handle ?? undefined,
    mission_id: String(t.mission_id ?? missionId),
    created_at: t.updated_at ?? "",
    updated_at: t.updated_at ?? "",
  }));
}

export function buildProjectsIndexRows(input: {
  checklistTasks: Task[];
  state: MissionControlStatePayload | null;
  workspaceProjects: WorkspaceProjectOut[];
}): Project[] {
  const { checklistTasks, state, workspaceProjects } = input;
  const missions = state && Array.isArray(state.missions) ? state.missions : [];
  const rawMissionTasks = state && Array.isArray(state.tasks) ? state.tasks : [];

  const checklistProgress = taskProgressPercent(checklistTasks);

  const rows: Project[] = [
    {
      id: CHECKLIST_PROJECT_ID,
      name: "My checklist",
      goal: "Personal tasks from GET /api/v1/tasks — drag cards to update status.",
      status: "active",
      progress: checklistProgress,
      kind_label: "Tasks",
    },
  ];

  for (const m of missions) {
    const o = m as Record<string, unknown>;
    const mid = String(o.id ?? "");
    if (!mid) continue;
    const title = String(o.title ?? `Mission ${mid}`);
    const inputText = typeof o.input_text === "string" ? o.input_text : "";
    const goal = inputText.trim() ? inputText.slice(0, 280) : "Mission execution board (read-only Kanban).";
    const missionTasks = missionTasksForMissionId(rawMissionTasks, mid);
    rows.push({
      id: missionProjectRouteId(mid),
      name: title,
      goal,
      status: missionCardStatus(String(o.status ?? "")),
      progress: taskProgressPercent(missionTasks),
      created_at: typeof o.created_at === "string" ? o.created_at : undefined,
      kind_label: "Mission",
    });
  }

  for (const p of workspaceProjects) {
    rows.push({
      id: workspaceProjectRouteId(p.id),
      name: p.name,
      goal: (p.description?.trim() || p.path_normalized || "Workspace folder mapping").slice(0, 400),
      status: "active",
      progress: 0,
      created_at: p.created_at ?? undefined,
      kind_label: "Workspace",
    });
  }

  return rows;
}
