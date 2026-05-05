"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { formatMissionControlApiError } from "@/lib/api";
import { clearMissionControlStateCache, fetchMissionControlState } from "@/lib/api/mission-control-state";
import { fetchWorkspaceProjects } from "@/lib/api/projects";
import { fetchTasksForKanban, updateTaskStatus } from "@/lib/api/tasks";
import {
  CHECKLIST_PROJECT_ID,
  missionProjectRouteId,
  missionTasksForMissionId,
  parseProjectsRouteSegment,
  taskProgressPercent,
  workspaceProjectRouteId,
} from "@/lib/mission-control-projects";
import type { KanbanColumnType, Project, Task } from "@/types/mission-control";
import { KanbanBoard } from "@/components/mission-control/Projects/KanbanBoard";
import { CreateTaskDialog } from "@/components/mission-control/Projects/CreateTaskDialog";
import { ProjectHeader } from "@/components/mission-control/Projects/ProjectHeader";
import { Button } from "@/components/ui/button";

function missionCardStatus(raw: string): Project["status"] {
  const s = (raw || "").toLowerCase();
  if (s === "completed") return "completed";
  if (s === "paused" || s === "cancelled") return "paused";
  if (s === "failed") return "archived";
  return "active";
}

export default function MissionControlProjectDetailPage() {
  const params = useParams();
  const segment = typeof params.id === "string" ? params.id : "";
  /** New object each call would change `load` every render → infinite useEffect loop. */
  const parsed = useMemo(() => parseProjectsRouteSegment(segment), [segment]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [mode, setMode] = useState<"checklist" | "mission" | "workspace" | "invalid">("invalid");

  const load = useCallback(async () => {
    if (!parsed) {
      setMode("invalid");
      setProject(null);
      setTasks([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (parsed.mode === "checklist") {
        const rows = await fetchTasksForKanban();
        setTasks(rows);
        setProject({
          id: CHECKLIST_PROJECT_ID,
          name: "My checklist",
          goal: "Personal tasks backed by PATCH /api/v1/tasks/{id}. Drag cards between columns to update status.",
          status: "active",
          progress: taskProgressPercent(rows),
          kind_label: "Tasks",
        });
        setMode("checklist");
        return;
      }

      if (parsed.mode === "mission") {
        const state = await fetchMissionControlState();
        const missions = state && Array.isArray(state.missions) ? state.missions : [];
        const rawMissionTasks = state && Array.isArray(state.tasks) ? state.tasks : [];
        const hit = missions.find((m) => String((m as { id?: unknown }).id ?? "") === parsed.missionId);
        if (!hit || typeof hit !== "object") {
          setMode("invalid");
          setProject(null);
          setTasks([]);
          return;
        }
        const o = hit as Record<string, unknown>;
        const title = String(o.title ?? `Mission ${parsed.missionId}`);
        const inputText = typeof o.input_text === "string" ? o.input_text : "";
        const goal = inputText.trim() ? inputText.slice(0, 400) : "Mission execution tasks from Mission Control state.";
        const mt = missionTasksForMissionId(rawMissionTasks, parsed.missionId);
        setTasks(mt);
        setProject({
          id: missionProjectRouteId(parsed.missionId),
          name: title,
          goal,
          status: missionCardStatus(String(o.status ?? "")),
          progress: taskProgressPercent(mt),
          created_at: typeof o.created_at === "string" ? o.created_at : undefined,
          kind_label: "Mission",
        });
        setMode("mission");
        return;
      }

      const wsList = await fetchWorkspaceProjects();
      const ws = wsList.find((p) => p.id === parsed.wsId);
      if (!ws) {
        setMode("invalid");
        setProject(null);
        setTasks([]);
        return;
      }
      setTasks([]);
      setProject({
        id: workspaceProjectRouteId(ws.id),
        name: ws.name,
        goal: (ws.description?.trim() || ws.path_normalized || "Workspace folder mapping").slice(0, 400),
        status: "active",
        progress: 0,
        created_at: ws.created_at ?? undefined,
        kind_label: "Workspace",
      });
      setMode("workspace");
    } catch (e) {
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
      setProject(null);
      setTasks([]);
      setMode("invalid");
    } finally {
      setLoading(false);
    }
  }, [parsed]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleTaskStatusChange = useCallback(async (taskId: string, newStatus: KanbanColumnType) => {
    await updateTaskStatus(taskId, newStatus);
    clearMissionControlStateCache();
    setTasks((prev) => {
      const next = prev.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t));
      setProject((p) => (p ? { ...p, progress: taskProgressPercent(next) } : null));
      return next;
    });
  }, []);


  if (loading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
        <p className="text-sm text-zinc-500">Loading…</p>
      </div>
    );
  }

  if (!parsed || mode === "invalid" || !project) {
    return (
      <div className="space-y-4">
        <ProjectHeader project={null} />
        {error ? (
          <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">{error}</div>
        ) : (
          <p className="text-zinc-400">Project not found.</p>
        )}
        <Button variant="outline" asChild>
          <Link href="/mission-control/projects">Back to projects</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <ProjectHeader
        project={project}
        actions={
          mode === "checklist" ? (
            <CreateTaskDialog projectId={project.id} onTaskCreated={load} />
          ) : mode === "workspace" ? (
            <Button variant="outline" size="sm" asChild>
              <Link href={`/mission-control/projects/${CHECKLIST_PROJECT_ID}`}>Open checklist board</Link>
            </Button>
          ) : null
        }
      />

      {error ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}

      {mode === "workspace" ? (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-400">
          <p className="font-medium text-zinc-200">Workspace project</p>
          <p className="mt-2">
            This card maps a host path for Nexa workspace workflows. Task Kanban and PATCH updates apply to{" "}
            <Link className="text-violet-400 underline-offset-4 hover:underline" href={`/mission-control/projects/${CHECKLIST_PROJECT_ID}`}>
              My checklist
            </Link>{" "}
            (GET/POST/PATCH <span className="text-zinc-300">/api/v1/tasks</span>). Mission boards remain execution snapshots from Mission
            Control state.
          </p>
        </div>
      ) : (
        <>
          {mode === "mission" ? (
            <p className="text-sm text-zinc-500">
              Mission tasks are read-only here — status changes are driven by execution. Drag-and-drop is disabled.
            </p>
          ) : null}
          <KanbanBoard
            tasks={tasks}
            readOnly={mode === "mission"}
            onTaskStatusChange={mode === "checklist" ? handleTaskStatusChange : undefined}
            onTasksRefresh={load}
          />
        </>
      )}
    </div>
  );
}
