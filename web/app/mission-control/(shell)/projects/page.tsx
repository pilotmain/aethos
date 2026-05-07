"use client";

import { useCallback, useEffect, useState } from "react";

import { formatMissionControlApiError } from "@/lib/api";
import { fetchMissionControlState } from "@/lib/api/mission-control-state";
import { fetchWorkspaceProjects } from "@/lib/api/projects";
import { fetchTasksForKanban } from "@/lib/api/tasks";
import { buildProjectsIndexRows } from "@/lib/mission-control-projects";
import type { Project } from "@/types/mission-control";
import { AssignmentsByAgentPanel } from "@/components/mission-control/Projects/AssignmentsByAgentPanel";
import { CreateProjectDialog } from "@/components/mission-control/Projects/CreateProjectDialog";
import { ProjectList } from "@/components/mission-control/Projects/ProjectList";

export default function MissionControlProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [state, checklistTasks, ws] = await Promise.all([
        fetchMissionControlState(),
        fetchTasksForKanban(),
        fetchWorkspaceProjects().catch(() => []),
      ]);
      setProjects(buildProjectsIndexRows({ checklistTasks, state, workspaceProjects: ws }));
    } catch (e) {
      setProjects([]);
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-50">Projects</h2>
          <p className="mt-1 max-w-xl text-sm text-zinc-400">
            Open your editable checklist board, inspect mission execution tasks (read-only Kanban), or manage AethOS workspace
            folder mappings.
          </p>
        </div>
        <CreateProjectDialog onCreated={load} />
      </div>

      {error ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">{error}</div>
      ) : null}

      <AssignmentsByAgentPanel />

      {loading ? (
        <div className="flex h-64 flex-col items-center justify-center gap-2">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
          <p className="text-sm text-zinc-500">Loading projects…</p>
        </div>
      ) : (
        <ProjectList projects={projects} />
      )}
    </div>
  );
}
