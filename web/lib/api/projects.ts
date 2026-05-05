import { apiFetch } from "@/lib/api/client";

/** GET /api/v1/web/workspace/nexa-projects */
export type WorkspaceProjectOut = {
  id: number;
  name: string;
  path_normalized: string;
  description: string | null;
  created_at: string | null;
};

export async function fetchWorkspaceProjects(): Promise<WorkspaceProjectOut[]> {
  const rows = await apiFetch<WorkspaceProjectOut[]>("/web/workspace/nexa-projects");
  return Array.isArray(rows) ? rows : [];
}

/** POST /api/v1/web/workspace/nexa-projects */
export async function createWorkspaceProject(payload: {
  path: string;
  name: string;
  description?: string | null;
}): Promise<WorkspaceProjectOut> {
  return apiFetch<WorkspaceProjectOut>("/web/workspace/nexa-projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
