import type { BudgetBand, BudgetInfo } from "@/types/mission-control";

import { apiFetch } from "@/lib/api/client";

/** Matches server default when env unset (`nexa_token_budget_per_day`). */
export const DEFAULT_DAILY_TOKEN_CAP = 100_000;

type ProviderUsagePayload = {
  summary?: {
    tokens_sent_today?: number;
    cost_estimate_usd_today?: number;
    budget_blocks_today?: number;
    local_calls_today?: number;
    external_calls_today?: number;
  };
};

function deriveStatus(percentage: number, blocksToday: number): BudgetBand {
  if (blocksToday > 0 || percentage >= 95) return "paused";
  if (percentage >= 80) return "warning";
  return "active";
}

/** GET /api/v1/providers/usage → summary from snapshot_for_user (Phase 38). */
export async function fetchBudgetInfo(dailyCap = DEFAULT_DAILY_TOKEN_CAP): Promise<BudgetInfo> {
  try {
    const data = await apiFetch<ProviderUsagePayload>("/providers/usage");
    const s = data.summary || {};
    const used = Number(s.tokens_sent_today ?? 0);
    const limit = Math.max(1, dailyCap);
    const percentage = Math.min(100, (used / limit) * 100);
    const remaining = Math.max(0, limit - used);
    const blocksToday = Number(s.budget_blocks_today ?? 0);
    return {
      used,
      limit,
      remaining,
      percentage,
      status: deriveStatus(percentage, blocksToday),
      blocksToday,
      costUsdToday: typeof s.cost_estimate_usd_today === "number" ? s.cost_estimate_usd_today : undefined,
    };
  } catch {
    return {
      used: 0,
      limit: dailyCap,
      remaining: dailyCap,
      percentage: 0,
      status: "active",
      blocksToday: 0,
    };
  }
}
