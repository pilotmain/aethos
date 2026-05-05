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

/** AethOS mission tasks embedded in Mission Control state (`tasks` array). */
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

/** Phase 33 M4 — Workspace / mission / checklist rows shown on the Projects index. */
export interface Project {
  /** URL segment under `/mission-control/projects/[id]` (e.g. `checklist`, `mission-12`, `ws-3`). */
  id: string;
  name: string;
  goal: string;
  status: "active" | "paused" | "completed" | "archived";
  progress: number;
  created_at?: string;
  updated_at?: string;
  completed_at?: string;
  team_scope?: string;
  /** Badge label for row kind */
  kind_label?: string;
}

/** Phase 33 M4 — Kanban task card (checklist tasks + mission tasks in read-only mode). */
export interface Task {
  id: string;
  title: string;
  description?: string;
  status: "pending" | "in_progress" | "done" | "blocked";
  assigned_to?: string;
  assigned_to_name?: string;
  project_id?: string;
  mission_id?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  order_index?: number;
}

export type KanbanColumnType = "pending" | "in_progress" | "done";

/** Phase 33 M5 — Budget & usage (derived from `/providers/usage` + user settings). */
export interface UsageRecord {
  date: string;
  tokens: number;
  cost: number;
  provider: string;
  model?: string;
}

export interface ProviderUsage {
  provider: string;
  /** Recharts `Pie` label key. */
  name?: string;
  tokens: number;
  cost: number;
  percentage: number;
}

export interface MemberUsage {
  member_id: string;
  member_name: string;
  tokens: number;
  cost: number;
  percentage: number;
  last_active: string;
}

export interface BudgetSettings {
  monthly_limit: number;
  daily_limit: number;
  current_usage: number;
  remaining: number;
  reset_day: number;
  alerts_enabled: boolean;
  warning_threshold: number;
  critical_threshold: number;
}

export interface BudgetAlert {
  id: string;
  type: "warning" | "critical" | "exceeded";
  message: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface UsageForecast {
  projected_total: number;
  projected_cost: number;
  days_remaining: number;
  estimated_daily_average: number;
  recommended_daily_cap: number;
}

/** Phase 33 M6 — Advanced settings (aligned with `/web/keys`, `/user/settings`, `/system/*`). */
export interface LLMProviderConfig {
  name: "openai" | "anthropic" | "deepseek" | "ollama";
  configured: boolean;
  model?: string;
  base_url?: string;
  status: "connected" | "disconnected" | "unknown";
  last_check?: string;
}

export interface IntegrationConfig {
  id: string;
  name: string;
  type: "slack" | "github" | "telegram" | "discord";
  enabled: boolean;
  configured: boolean;
  webhook_url?: string;
  channel?: string;
  last_active?: string;
}

export interface SystemConfig {
  workspace_root: string;
  sandbox_mode: boolean;
  network_policy_strict: boolean;
  approvals_enabled: boolean;
  autonomous_mode: boolean;
  log_level: "debug" | "info" | "warning" | "error";
  data_dir: string;
}

export interface DiagnosticInfo {
  api_status: "healthy" | "degraded" | "down";
  database_status: "healthy" | "error";
  cron_status: "running" | "stopped";
  workers: number;
  uptime_seconds: number;
  version: string;
}
