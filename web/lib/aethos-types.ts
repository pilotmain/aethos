/** GET /api/v1/reports/status — workspace report watcher / mission_control.md mtime. */
export type ReportsStatus = {
  enabled: boolean;
  reports_dir: string;
  mission_control_mtime: number | null;
  ui_update_event_mtime: number | null;
  ui_event: Record<string, unknown> | null;
};

/** GET /api/v1/reports/mission-control */
export type ReportsMissionControl = {
  markdown: string;
  mission_control_mtime: number | null;
};

/** Shapes for /api/v1/web responses (subset; matches backend JSON). */
export type AethosJob = {
  id: number;
  user_id: string;
  source: string;
  kind: string;
  worker_type: string;
  title: string;
  instruction: string;
  command_type?: string | null;
  status: string;
  approval_required: boolean;
  risk_level: string | null;
  payload_json: {
    project_key?: string;
    host_action?: string;
    run_name?: string;
    relative_path?: string;
    execution_decision?: {
      tool_key?: string;
      mode?: string;
      risk_level?: string;
    };
  };
  result: string | null;
  error_message: string | null;
};

export type WebResponseSource = {
  url: string;
  title: string | null;
};

export type UsageSummary = {
  used_llm: boolean;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number | null;
  provider: string | null;
  model: string | null;
  used_user_key: boolean;
  /** Multi-call turn: token % split, free (Ollama) vs paid (cloud), with model ids */
  mix_display?: string | null;
  subline?: string | null;
};

export type WebMe = {
  app_user_id: string;
  telegram_user_id: string | null;
  username: string | null;
  is_owner: boolean;
  show_cost_details_default: boolean;
};

/** GET /api/v1/governance/me — feature flag + org list. */
export type GovernanceMe = {
  governance_enabled: boolean;
  default_organization_id: string | null;
  organizations: { id: string; name: string; enabled: boolean }[];
};

/** GET /api/v1/governance/organizations/{org_id}/overview */
export type GovernanceOrgOverview = {
  organization: { id: string; name: string; enabled?: boolean };
  current_user_role: string;
  members: { user_id: string; role: string; enabled: boolean }[];
  audit_summary: {
    events_24h: number;
    permission_requests: number;
    denied_actions: number;
  };
  recent_events: unknown[];
  policies: Record<string, unknown>;
};

/** GET /api/v1/governance/overview?organization_id= — channel matrix + retention (may 403 for non-admin). */
export type EnterpriseChannelGovernanceOverview = {
  organization_id: string;
  retention_days: number;
  policies: { channel: string; enabled: boolean; allowed_roles: string[]; approval_required: boolean }[];
  channels: ChannelStatus[];
};

export type DecisionSummary = {
  agent: string;
  action: string;
  tool: string | null;
  reason: string;
  risk: string;
  approval_required: boolean;
  intent?: string | null;
};

export type SystemEventItem = {
  kind: string;
  text: string;
};

/** Inline host permission card from POST /web/chat when access grant is missing. */
export type PermissionRequiredPayload = {
  type: "permission_required";
  permission_request_id: string;
  scope: string;
  target: string;
  reason: string;
  risk_level: string;
  grant_options: string[];
  message?: string;
};

export type WebChatRes = {
  reply: string;
  intent: string | null;
  agent_key: string | null;
  related_jobs: AethosJob[];
  response_kind?: string | null;
  permission_required?: PermissionRequiredPayload | null;
  sources?: WebResponseSource[];
  web_tool_line?: string | null;
  usage_summary?: UsageSummary | null;
  request_id?: string | null;
  decision_summary?: DecisionSummary | null;
  system_events?: SystemEventItem[];
};

export type WebWorkContext = {
  flow: {
    has_flow: boolean;
    expired: boolean;
    goal: string | null;
    total_steps: number;
    completed_steps: number;
    next_command: string | null;
  };
  lines: string[];
  recent_artifacts: { kind: string; id: number; label: string }[];
};

export type WebSessionRow = {
  id: string;
  title: string;
  summary: string | null;
  last_agent: string | null;
  last_intent: string | null;
  message_count: number;
  active_topic: string | null;
  updated_at?: string | null;
  preview?: string | null;
};

export type SystemIndicator = {
  id: string;
  label: string;
  level: string;
  detail: string | null;
};

/** GET /api/v1/channels/status — gateway channel visibility (no secrets). */
export type ChannelStatus = {
  channel: string;
  label: string;
  available: boolean;
  configured: boolean;
  enabled: boolean;
  health: "ok" | "missing_config" | "disabled" | "unknown";
  webhook_url?: string | null;
  webhook_urls?: Record<string, string | null> | null;
  missing: string[];
  notes?: string[];
  /** In-memory last outbound / error hints (Phase 12) when available. */
  health_details?: Record<string, string> | null;
  /** Phase 13 — when governance is on and org context is resolved. */
  governance_enabled?: boolean | null;
  allowed_roles?: string[] | null;
  approval_required?: boolean | null;
  /** Mission Control: trust-like events in window for this channel label */
  recent_event_count?: number;
};

export type ChannelsStatusResponse = {
  channels: ChannelStatus[];
};

/** Orchestration slice included in GET /api/v1/mission-control/state */
export type OrchestrationSummary = {
  organization: { id: number; name: string; enabled: boolean } | null;
  roles: {
    agent_handle: string;
    agent_handle_display?: string;
    role: string;
    reports_to_handle: string | null;
    reports_to_handle_display?: string | null;
    enabled: boolean;
  }[];
  assignments: {
    id: number;
    assigned_to_handle: string;
    assigned_to_handle_display?: string;
    title: string;
    status: string;
    spawn_group_id?: string | null;
    input_json?: Record<string, unknown> | null;
    /** Cursor Cloud Agents (when assignment ran via Nexa → Cursor). */
    cursor_run_id?: string | null;
    cursor_status?: string | null;
    cursor_repo?: string | null;
    cursor_branch?: string | null;
    cursor_cost_estimate?: unknown;
  }[];
};

export type MissionControlSummary = {
  overview: {
    active_jobs: number;
    pending_approvals: number;
    blocked_actions: number;
    high_risk_events: number;
    active_channels: number;
    recent_executions: number;
  };
  attention: MissionControlItem[];
  active_work: MissionControlItem[];
  pending_approvals: MissionControlItem[];
  risk_summary: Record<string, unknown>;
  channels: ChannelStatus[];
  recommendations: MissionControlItem[];
  quiet?: boolean;
  hours?: number;
  /** Agent team + durable assignments (orchestration layer). */
  orchestration?: OrchestrationSummary;
  /** Server capabilities for Mission Control maintenance UI. */
  maintenance?: {
    sql_purge_enabled?: boolean;
  };
};

export type MissionControlItem = {
  id: string;
  type: string;
  title: string;
  description?: string | null;
  status?: string | null;
  risk_level?: string | null;
  channel?: string | null;
  score?: number;
  created_at?: string | null;
  permission_id?: number | null;
  job_id?: number | null;
  scope?: string | null;
  target?: string | null;
  reason?: string | null;
  agent?: string | null;
  started_at?: string | null;
  updated_at?: string | null;
};

/** GET /api/v1/custom-agents — user-defined agents (Phase 20/21). */
export type CustomAgent = {
  handle: string;
  display_name: string;
  description?: string;
  safety_level?: string;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
};

export type CustomAgentsListOut = {
  agents: CustomAgent[];
};

/** Safe host executor snapshot from GET /web/system/status */
export type WebHostExecutorPanel = {
  enabled: boolean;
  work_root: string;
  allowed_host_actions: string[];
  allowed_run_names: string[];
  timeout_seconds: number;
  max_file_bytes: number;
};

export type WebReleaseNotes = {
  release_id: string;
  date: string;
  title: string;
  items: string[];
  full_text: string;
};

/** Authenticated GET /web/release/latest — banner + optional inline detail. */
export type WebReleaseLatest = {
  release_id: string;
  items: string[];
  full_text: string;
};

export type MemoryState = {
  preferences: { planning_style: string; max_daily_tasks: number; typical_gym_days: string[] };
  notes: { key: string; category: string; content: string; summary: string; source: string }[];
  soul_markdown: string;
  memory_markdown: string;
};

export type LlmUsageSummary = {
  period: string;
  time_start_utc?: string | null;
  time_end_utc?: string | null;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  system_key_cost_usd: number;
  user_key_cost_usd: number;
  by_provider: { provider: string; calls: number; input_tokens: number; output_tokens: number; total_tokens: number; estimated_cost_usd: number }[];
  by_agent: { agent: string; calls: number; input_tokens: number; output_tokens: number; total_tokens: number; estimated_cost_usd: number }[];
  by_action: {
    action: string;
    calls: number;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    estimated_cost_usd: number;
    percent?: number;
    cost?: number;
  }[];
  top_cost_drivers?: { action: string; count: number; cost: number; percent: number }[];
  efficiency?: {
    total_actions: number;
    llm_calls: number;
    non_llm_actions: number;
    efficiency_ratio: number | null;
  };
};

export type SessionUsageSummary = {
  session_id: string;
  total_tokens: number;
  total_cost_usd: number | null;
  call_count: number;
};

export type LlmUsageRecent = {
  at: string | null;
  provider: string;
  model: string | null;
  source: string;
  agent: string | null;
  action: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number | null;
  used_user_key: boolean;
  success: boolean;
  error_type: string | null;
};

export type LlmUsageRecentResponse = { items: LlmUsageRecent[] };

/** `/api/v1/trust/*` — matches backend read model (P1). */
export type TrustUiStatus = "allowed" | "blocked" | "warning";

export type TrustEventRow = {
  id: number;
  event_type: string;
  actor: string;
  message: string;
  user_id: string | null;
  job_id: number | null;
  created_at: string | null;
  metadata: Record<string, unknown>;
  workflow_id?: string | null;
  run_id?: string | null;
  execution_id?: string | null;
  status: TrustUiStatus;
  destination: string | null;
  sensitivity_level?: string | null;
  /** Origin surface when present (audit metadata); null / omitted for legacy rows. */
  channel?: string | null;
  channel_user_id?: string | null;
  channel_message_id?: string | null;
  channel_thread_id?: string | null;
  channel_chat_id?: string | null;
};

export type TrustActivityResponse = {
  since: string;
  hours: number;
  event_types_filter: string[] | null;
  events: TrustEventRow[];
};

export type TrustSummaryResponse = {
  window_hours: number;
  counts: {
    permission_uses: number;
    network_external_send_allowed: number;
    network_external_send_blocked: number;
    sensitive_egress_warnings: number;
    host_executor_blocks: number;
    safety_enforcement_paths: number;
  };
  recent_events: TrustEventRow[];
};
