/** Derive team counts from Mission Control state (`orchestration` slice). */

import type { OrgChartNode, TeamMember, TeamMemberStatus } from "@/types/mission-control";

import type { OrgMemberRow } from "@/lib/api/governance";

export type TeamMetrics = { total: number; active: number };

export type AgentRoleRow = {
  agent_handle: string;
  agent_handle_display?: string | null;
  role: string;
  reports_to_handle?: string | null;
  enabled?: boolean;
};

export type SubAgentOrchestrationRow = Record<string, unknown>;

/** Registry-backed orchestration agents from ``GET /mission-control/state`` → ``orchestration.sub_agents``. */
export function parseSubAgents(raw: unknown): SubAgentOrchestrationRow[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter((x) => x && typeof x === "object") as SubAgentOrchestrationRow[];
}

export function teamMetricsFromState(state: Record<string, unknown> | null): TeamMetrics {
  if (!state) return { total: 0, active: 0 };
  const orch = state.orchestration as
    | { roles?: unknown[]; assignments?: unknown[]; sub_agents?: unknown[] }
    | undefined;
  const roles = Array.isArray(orch?.roles) ? orch.roles : [];
  const assigns = Array.isArray(orch?.assignments) ? orch.assignments : [];
  const subAgents = parseSubAgents(orch?.sub_agents);
  const active = assigns.filter((a) => {
    const st = String((a as { status?: string }).status || "").toLowerCase();
    return st && st !== "cancelled";
  }).length;
  const roleHandles = new Set(
    roles.map((r) => String((r as { agent_handle?: string }).agent_handle || "").trim()).filter(Boolean),
  );
  const subHandles = new Set(
    subAgents.map((s: SubAgentOrchestrationRow) => String(s.name ?? "").trim()).filter(Boolean),
  );
  const mergedHandles = new Set<string>([
    ...Array.from(roleHandles),
    ...Array.from(subHandles),
  ]);
  const total = Math.max(mergedHandles.size, roles.length, subAgents.length);
  return { total, active: active || assigns.length };
}

const BUSY = new Set(["running", "in_progress", "queued", "assigned", "active"]);

function statusForAgent(handle: string, assignments: unknown[]): TeamMemberStatus {
  const h = (handle || "").trim().toLowerCase();
  for (const a of assignments) {
    if (!a || typeof a !== "object") continue;
    const o = a as Record<string, unknown>;
    const ah = String(o.assigned_to_handle || "").trim().toLowerCase();
    if (ah !== h) continue;
    const st = String(o.status || "").toLowerCase();
    if (BUSY.has(st)) return "busy";
  }
  return "active";
}

function parseAgentRoles(raw: unknown): AgentRoleRow[] {
  if (!Array.isArray(raw)) return [];
  const out: AgentRoleRow[] = [];
  for (const r of raw) {
    if (!r || typeof r !== "object") continue;
    const o = r as Record<string, unknown>;
    const ah = String(o.agent_handle ?? "").trim();
    if (!ah) continue;
    out.push({
      agent_handle: ah,
      agent_handle_display: o.agent_handle_display != null ? String(o.agent_handle_display) : undefined,
      role: String(o.role ?? "member"),
      reports_to_handle: o.reports_to_handle != null ? String(o.reports_to_handle) : null,
      enabled: o.enabled !== false,
    });
  }
  return out;
}

/** Build tree from `reports_to_handle` edges (agent org). */
export function buildAgentOrgChart(roles: AgentRoleRow[]): OrgChartNode[] {
  const rows = roles.filter((r) => r.enabled !== false);
  if (!rows.length) return [];
  const byHandle = new Map(rows.map((r) => [r.agent_handle.toLowerCase(), r]));
  const children = new Map<string, AgentRoleRow[]>();
  for (const r of rows) {
    const parent = (r.reports_to_handle || "").trim();
    const pKey = parent.toLowerCase();
    if (!parent || !byHandle.has(pKey)) continue;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent)!.push(r);
  }
  const roots = rows.filter((r) => {
    const parent = (r.reports_to_handle || "").trim();
    if (!parent) return true;
    return !byHandle.has(parent.toLowerCase());
  });

  function toNode(r: AgentRoleRow): OrgChartNode {
    const ch = children.get(r.agent_handle) || [];
    return {
      id: r.agent_handle,
      name: r.agent_handle_display || r.agent_handle,
      role: r.role,
      children: ch.map(toNode),
      metadata: { reports_to: r.reports_to_handle },
    };
  }

  return roots.map(toNode);
}

export function agentRolesToTeamMembers(
  roles: AgentRoleRow[],
  assignments: unknown[],
): TeamMember[] {
  const now = new Date().toISOString();
  return roles
    .filter((r) => r.enabled !== false)
    .map((r) => {
      const st = statusForAgent(r.agent_handle, assignments);
      const task = pickAssignmentTitle(r.agent_handle, assignments);
      return {
        kind: "agent",
        id: `agent:${r.agent_handle}`,
        name: r.agent_handle_display || r.agent_handle,
        user_id: r.agent_handle,
        roleKey: "agent_role",
        roleLabel: r.role,
        status: st,
        current_task: task,
        joined_at: now,
        last_active: task ? now : undefined,
      } satisfies TeamMember;
    });
}

function pickAssignmentTitle(handle: string, assignments: unknown[]): string | undefined {
  const h = handle.trim().toLowerCase();
  for (const a of assignments) {
    if (!a || typeof a !== "object") continue;
    const o = a as Record<string, unknown>;
    if (String(o.assigned_to_handle || "").trim().toLowerCase() !== h) continue;
    const t = o.title;
    if (typeof t === "string" && t.trim()) return t.trim().slice(0, 180);
  }
  return undefined;
}

function normalizeGovRole(r: string): TeamMember["roleKey"] {
  const x = (r || "").toLowerCase();
  if (x === "owner") return "owner";
  if (x === "admin") return "admin";
  if (x === "viewer") return "viewer";
  if (x === "auditor") return "auditor";
  return "member";
}

export function governanceRowsToTeamMembers(
  rows: OrgMemberRow[],
  orgId: string,
): TeamMember[] {
  const now = new Date().toISOString();
  return rows.map((m) => ({
    kind: "human",
    id: `human:${m.user_id}`,
    name: m.user_id,
    user_id: m.user_id,
    roleKey: normalizeGovRole(m.role),
    roleLabel: m.role,
    status: m.enabled ? "active" : "offline",
    joined_at: now,
    governance: { org_id: orgId, enabled: m.enabled },
  }));
}

/** Turn registry payloads into the same shape as agent-org ``roles`` rows for Team UI merging. */
export function subAgentsToAgentRoles(rows: SubAgentOrchestrationRow[]): AgentRoleRow[] {
  const out: AgentRoleRow[] = [];
  for (const r of rows) {
    const name = String(r.name ?? "").trim();
    if (!name) continue;
    const domain = String(r.domain ?? "general").trim() || "general";
    out.push({
      agent_handle: name,
      agent_handle_display: name,
      role: domain,
      reports_to_handle: null,
      enabled: true,
    });
  }
  return out;
}

/** Merge org chart roles with orchestration registry agents; registry rows win on duplicate handles. */
export function mergeAgentRoles(orgRoles: AgentRoleRow[], registryRoles: AgentRoleRow[]): AgentRoleRow[] {
  const by = new Map<string, AgentRoleRow>();
  for (const r of orgRoles) by.set(r.agent_handle.toLowerCase(), r);
  for (const r of registryRoles) by.set(r.agent_handle.toLowerCase(), r);
  return Array.from(by.values());
}

/** Extract roles, assignments, and registry sub-agents from Mission Control state. */
export function orchestrationFromState(state: Record<string, unknown> | null): {
  roles: AgentRoleRow[];
  assignments: unknown[];
  subAgents: SubAgentOrchestrationRow[];
} {
  const orch = state?.orchestration as
    | { roles?: unknown[]; assignments?: unknown[]; sub_agents?: unknown[] }
    | undefined;
  return {
    roles: parseAgentRoles(orch?.roles),
    assignments: Array.isArray(orch?.assignments) ? orch.assignments : [],
    subAgents: parseSubAgents(orch?.sub_agents),
  };
}
