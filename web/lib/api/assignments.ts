/**
 * Agent assignments — wraps :code:`/api/v1/agent-assignments`.
 *
 * The POST endpoint runs ``dispatch_assignment`` immediately when the body omits
 * ``auto_dispatch`` (see :data:`NEXA_ASSIGNMENT_AUTO_DISPATCH_DEFAULT`); the response
 * carries an extra ``auto_dispatch`` field with the dispatch result.
 */

import { apiFetch } from "@/lib/api/client";

export type AgentAssignmentRow = {
  id: number;
  user_id: string;
  organization_id: number | null;
  parent_assignment_id: number | null;
  assigned_to_handle: string;
  assigned_to_handle_display?: string | null;
  assigned_by_handle: string;
  assigned_by_handle_display?: string | null;
  title: string;
  description: string;
  status: string;
  priority: string;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown> | null;
  error: string | null;
  channel: string;
  web_session_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type AgentAssignmentDispatchResult = {
  ok?: boolean;
  error?: string;
  assignment_id?: number;
  output?: Record<string, unknown>;
  waiting_approval?: boolean;
  waiting_worker?: boolean;
};

export type AgentAssignmentCreateResponse = AgentAssignmentRow & {
  /** Present only when auto-dispatch ran on POST; absent when caller passed auto_dispatch=false. */
  auto_dispatch?: AgentAssignmentDispatchResult;
};

export type AgentAssignmentCreatePayload = {
  assigned_to_handle: string;
  title: string;
  description?: string;
  priority?: string;
  input_json?: Record<string, unknown>;
  organization_id?: number | null;
  /** When omitted server falls back to NEXA_ASSIGNMENT_AUTO_DISPATCH_DEFAULT (true by default). */
  auto_dispatch?: boolean;
};

export async function fetchAgentAssignments(): Promise<AgentAssignmentRow[]> {
  const data = await apiFetch<{ assignments?: AgentAssignmentRow[] }>("/agent-assignments");
  return Array.isArray(data?.assignments) ? data.assignments : [];
}

export async function createAgentAssignment(
  payload: AgentAssignmentCreatePayload,
): Promise<AgentAssignmentCreateResponse> {
  return apiFetch<AgentAssignmentCreateResponse>("/agent-assignments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function dispatchAgentAssignment(
  assignmentId: number,
): Promise<AgentAssignmentDispatchResult> {
  return apiFetch<AgentAssignmentDispatchResult>(
    `/agent-assignments/${encodeURIComponent(String(assignmentId))}/dispatch`,
    { method: "POST" },
  );
}

export async function cancelAgentAssignment(
  assignmentId: number,
): Promise<AgentAssignmentDispatchResult> {
  return apiFetch<AgentAssignmentDispatchResult>(
    `/agent-assignments/${encodeURIComponent(String(assignmentId))}/cancel`,
    { method: "POST" },
  );
}

export type AssignmentsByAgent = Record<string, AgentAssignmentRow[]>;

/** Group assignments by ``assigned_to_handle`` (display label preferred when present). */
export function groupAssignmentsByAgent(rows: AgentAssignmentRow[]): AssignmentsByAgent {
  const out: AssignmentsByAgent = {};
  for (const row of rows) {
    const key = (row.assigned_to_handle_display || row.assigned_to_handle || "unassigned").trim() || "unassigned";
    if (!out[key]) out[key] = [];
    out[key].push(row);
  }
  return out;
}

const TERMINAL = new Set(["completed", "failed", "cancelled"]);
const RUNNING = new Set(["running", "queued", "assigned", "waiting_worker", "waiting_approval"]);

export function summarizeAssignments(rows: AgentAssignmentRow[]): {
  total: number;
  running: number;
  completed: number;
  failed: number;
} {
  let running = 0;
  let completed = 0;
  let failed = 0;
  for (const r of rows) {
    const s = (r.status || "").toLowerCase();
    if (s === "completed") completed += 1;
    else if (s === "failed") failed += 1;
    else if (RUNNING.has(s)) running += 1;
  }
  return { total: rows.length, running, completed, failed };
}

export function isAssignmentTerminal(status: string): boolean {
  return TERMINAL.has((status || "").toLowerCase());
}
