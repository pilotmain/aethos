/**
 * Orchestration sub-agents — Mission Control state first, then ``GET /agents/list`` (via apiFetch).
 */

import { apiFetch } from "@/lib/api/client";
import { fetchMissionControlState } from "@/lib/api/mission-control-state";
import { orchestrationFromState } from "@/lib/api/team";

export type OrchestrationAgentRow = Record<string, unknown>;

export async function fetchAgentsList(): Promise<OrchestrationAgentRow[]> {
  const data = await apiFetch<{ agents?: OrchestrationAgentRow[] }>("/agents/list");
  return Array.isArray(data.agents) ? data.agents : [];
}

/**
 * Prefer ``orchestration.sub_agents`` from GET /mission-control/state; if empty, fall back to
 * ``/agents/list`` (same merged scopes as API). Pass ``existingState`` when the caller already
 * fetched state to avoid an extra round-trip (cache still applies inside fetchMissionControlState).
 */
export async function fetchOrchestrationAgentsResolved(
  hours = 48,
  existingState?: Record<string, unknown> | null,
): Promise<OrchestrationAgentRow[]> {
  let state: Record<string, unknown> | null | undefined = existingState;
  if (existingState === undefined) {
    state = await fetchMissionControlState(hours).catch(() => null);
  }
  if (state) {
    const { subAgents } = orchestrationFromState(state);
    if (subAgents.length > 0) {
      return subAgents as OrchestrationAgentRow[];
    }
  }
  return fetchAgentsList();
}
