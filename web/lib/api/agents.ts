/**
 * Orchestration sub-agents from ``GET /api/v1/agents/list`` (same registry as Telegram/web gateway).
 */

import { apiFetch } from "@/lib/api/client";

export type OrchestrationAgentRow = Record<string, unknown>;

export async function fetchAgentsList(): Promise<OrchestrationAgentRow[]> {
  const data = await apiFetch<{ agents?: OrchestrationAgentRow[] }>("/agents/list");
  return Array.isArray(data.agents) ? data.agents : [];
}
