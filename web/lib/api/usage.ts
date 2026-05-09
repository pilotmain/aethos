import { apiFetch } from "@/lib/api/client";

/** GET /api/v1/providers/usage — Phase 38 token audit tail + `snapshot_for_user` roll-up. */
export type ProviderUsageCall = {
  provider?: string | null;
  model?: string | null;
  token_estimate?: number | null;
  cost_estimate_usd?: number | null;
  payload_summary?: Record<string, unknown> | null;
  redactions?: unknown;
  blocked?: boolean | null;
  block_reason?: string | null;
};

export type ProviderUsageSummary = {
  tokens_sent_today?: number;
  cost_estimate_usd_today?: number;
  local_calls_today?: number;
  external_calls_today?: number;
  budget_blocks_today?: number;
  last_payload_summary?: unknown;
  last_redactions_count?: number;
};

export type ProviderUsageResponse = {
  ok?: boolean;
  calls: ProviderUsageCall[];
  summary: ProviderUsageSummary;
  /** Full DB-backed roll-up (same source as `/web/usage/summary`). */
  llm_summary?: Record<string, unknown>;
};

export async function fetchProviderUsage(): Promise<ProviderUsageResponse> {
  return apiFetch<ProviderUsageResponse>("/providers/usage");
}
