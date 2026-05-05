/**
 * Phase 33 — Overview dashboard types (aligned with GET /api/v1/mission-control/state and related APIs).
 */

/** Checklist tasks from GET /api/v1/tasks (TaskRead). */
export type OverviewChecklistTask = {
  id: string;
  title: string;
  description?: string | null;
  status: "pending" | "in_progress" | "done" | "blocked";
  assigned_to?: string;
  assigned_to_name?: string;
  project_id?: string;
  created_at: string;
  updated_at: string;
};

/** Nexa mission tasks embedded in Mission Control state (`tasks` array). */
export type OverviewMissionTask = {
  id: string;
  mission_id?: string | null;
  title: string;
  status: "pending" | "in_progress" | "done" | "blocked";
  agent_handle?: string | null;
  updated_at?: string | null;
};

export type BudgetBand = "active" | "warning" | "paused";

export type BudgetInfo = {
  used: number;
  limit: number;
  remaining: number;
  percentage: number;
  status: BudgetBand;
  /** Blocks recorded today (token economy). */
  blocksToday: number;
  costUsdToday?: number;
};

export type SystemHealthFlags = {
  api: boolean;
  /** Heuristic: user has at least one enabled scheduler job. */
  cron: boolean;
  /** Heuristic: remote LLM providers configured / not offline-only. */
  providers: boolean;
};

export type AttentionActivityItem = {
  id: string;
  type: string;
  title: string;
  description?: string;
  created_at?: string | null;
};

export type DashboardBundle = {
  projects: { total: number; active: number };
  team: { total: number; active: number };
  budget: BudgetInfo;
  health: SystemHealthFlags;
  checklistTasks: OverviewChecklistTask[];
  missionTasks: OverviewMissionTask[];
  attention: AttentionActivityItem[];
  quiet?: boolean;
};

/** Phase 33 M3 — Team view (agents + optional governance members). */
export type TeamMemberStatus = "active" | "busy" | "idle" | "offline";

export type GovernanceRoleKey = "owner" | "admin" | "member" | "viewer" | "auditor";

export interface TeamMember {
  kind: "agent" | "human";
  id: string;
  name: string;
  user_id: string;
  /** Normalized when possible for styling (governance). */
  roleKey: GovernanceRoleKey | "agent_role";
  /** Raw role label from API (always shown). */
  roleLabel: string;
  status: TeamMemberStatus;
  current_task?: string;
  joined_at: string;
  last_active?: string;
  avatar?: string;
  /** When `human`, PATCH targets this org. */
  governance?: { org_id: string; enabled: boolean };
}

export interface OrgChartNode {
  id: string;
  name: string;
  role: string;
  children: OrgChartNode[];
  metadata?: Record<string, unknown>;
}
