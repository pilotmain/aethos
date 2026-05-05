import type {
  BudgetAlert,
  BudgetBand,
  BudgetInfo,
  BudgetSettings,
  MemberUsage,
  ProviderUsage,
  UsageForecast,
  UsageRecord,
} from "@/types/mission-control";

import { apiFetch } from "@/lib/api/client";
import type { ProviderUsageCall, ProviderUsageResponse, ProviderUsageSummary } from "@/lib/api/usage";
import { fetchProviderUsage } from "@/lib/api/usage";

/** Matches server default when env unset (`nexa_token_budget_per_day`). */
export const DEFAULT_DAILY_TOKEN_CAP = 100_000;

const LS_ALERT_ACK = "nexa-mc-budget-alert-acks";

export type UserBudgetPreferences = {
  ui_preferences?: Record<string, unknown>;
  token_budget_per_request?: number | null;
  daily_cost_budget_usd?: number | null;
};

export type BudgetDashboardData = {
  usageHistory: UsageRecord[];
  dailyBars: { date: string; label: string; tokens: number; cost: number }[];
  providerBreakdown: ProviderUsage[];
  memberUsage: MemberUsage[];
  alerts: BudgetAlert[];
  settings: BudgetSettings;
  forecast: UsageForecast;
  budgetInfo: BudgetInfo;
  /** Set when `/providers/usage` fails (e.g. auth); partial data still returned. */
  loadError?: string;
};

function deriveStatus(percentage: number, blocksToday: number): BudgetBand {
  if (blocksToday > 0 || percentage >= 95) return "paused";
  if (percentage >= 80) return "warning";
  return "active";
}

export function budgetInfoFromSummary(summary: ProviderUsageSummary | undefined, dailyCap: number): BudgetInfo {
  const s = summary || {};
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
}

/** GET /api/v1/providers/usage → summary from snapshot_for_user (Phase 38). */
export async function fetchBudgetInfo(dailyCap = DEFAULT_DAILY_TOKEN_CAP): Promise<BudgetInfo> {
  try {
    const data = await fetchProviderUsage();
    return budgetInfoFromSummary(data.summary, dailyCap);
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

/** GET /api/v1/user/settings — persisted token/cost UI preferences (Phase 20 + 38). */
export async function fetchUserBudgetPreferences(): Promise<UserBudgetPreferences> {
  return apiFetch<UserBudgetPreferences>("/user/settings");
}

/** POST /api/v1/user/settings — merges `ui_preferences` and accepts root token fields. */
export async function patchUserBudgetSettings(payload: {
  token_budget_per_request?: number;
  daily_cost_budget_usd?: number;
  ui_preferences?: Record<string, unknown>;
}): Promise<UserBudgetPreferences> {
  return apiFetch<UserBudgetPreferences>("/user/settings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function callsToUsageRecords(calls: ProviderUsageCall[], summary: ProviderUsageSummary): UsageRecord[] {
  const now = Date.now();
  if (!calls.length) {
    const d = `${new Date().toISOString().slice(0, 10)}T12:00:00.000Z`;
    return [
      {
        date: d,
        tokens: Number(summary.tokens_sent_today ?? 0),
        cost: Number(summary.cost_estimate_usd_today ?? 0),
        provider: "today",
      },
    ];
  }
  return calls.map((c, i) => ({
    date: new Date(now - (calls.length - 1 - i) * 60_000).toISOString(),
    tokens: Number(c.token_estimate ?? 0),
    cost: Number(c.cost_estimate_usd ?? 0),
    provider: String(c.provider ?? "unknown"),
    model: typeof c.model === "string" ? c.model : undefined,
  }));
}

export function rollupUsageByDay(records: UsageRecord[]): UsageRecord[] {
  const map = new Map<string, { tokens: number; cost: number }>();
  for (const r of records) {
    const day = r.date.slice(0, 10);
    const prev = map.get(day) || { tokens: 0, cost: 0 };
    map.set(day, { tokens: prev.tokens + r.tokens, cost: prev.cost + r.cost });
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, v]) => ({
      date: `${day}T00:00:00.000Z`,
      tokens: v.tokens,
      cost: v.cost,
      provider: "mixed",
    }));
}

export function buildProviderBreakdown(records: UsageRecord[]): ProviderUsage[] {
  const tally = new Map<string, { tokens: number; cost: number }>();
  for (const r of records) {
    const p = (r.provider || "unknown").trim() || "unknown";
    const cur = tally.get(p) || { tokens: 0, cost: 0 };
    tally.set(p, { tokens: cur.tokens + r.tokens, cost: cur.cost + r.cost });
  }
  const totalTokens = Array.from(tally.values()).reduce((s, x) => s + x.tokens, 0) || 1;
  return Array.from(tally.entries())
    .map(([provider, v]) => ({
      provider,
      name: provider,
      tokens: v.tokens,
      cost: v.cost,
      percentage: (v.tokens / totalTokens) * 100,
    }))
    .sort((a, b) => b.tokens - a.tokens);
}

export function providersToMemberUsage(providers: ProviderUsage[]): MemberUsage[] {
  const iso = new Date().toISOString();
  return providers.map((p) => ({
    member_id: p.provider,
    member_name:
      p.provider === "today" || p.provider === "mixed" ? "Roll-up / mixed" : p.provider,
    tokens: p.tokens,
    cost: p.cost,
    percentage: p.percentage,
    last_active: iso,
  }));
}

export function buildBudgetSettings(
  summary: ProviderUsageSummary,
  prefs: UserBudgetPreferences | null,
  dailyCap: number,
): BudgetSettings {
  const ui = (prefs?.ui_preferences || {}) as Record<string, unknown>;
  const monthlyDefault = dailyCap * 30;
  const monthly =
    typeof ui.monthly_token_target === "number" && Number.isFinite(ui.monthly_token_target)
      ? Number(ui.monthly_token_target)
      : monthlyDefault;
  const warn =
    typeof ui.budget_warning_threshold_pct === "number" && Number.isFinite(ui.budget_warning_threshold_pct)
      ? Math.min(95, Math.max(50, Number(ui.budget_warning_threshold_pct)))
      : 80;
  const crit =
    typeof ui.budget_critical_threshold_pct === "number" && Number.isFinite(ui.budget_critical_threshold_pct)
      ? Math.min(99, Math.max(warn + 1, Number(ui.budget_critical_threshold_pct)))
      : 95;
  const alertsEnabled = ui.budget_alerts_enabled !== false;
  const used = Number(summary.tokens_sent_today ?? 0);
  return {
    monthly_limit: Math.round(monthly),
    daily_limit: dailyCap,
    current_usage: used,
    remaining: Math.max(0, dailyCap - used),
    reset_day: 1,
    alerts_enabled: alertsEnabled,
    warning_threshold: warn,
    critical_threshold: crit,
  };
}

export function buildBudgetAlerts(budgetInfo: BudgetInfo, settings: BudgetSettings): BudgetAlert[] {
  const ts = new Date().toISOString();
  const out: BudgetAlert[] = [];
  if (budgetInfo.blocksToday > 0) {
    out.push({
      id: "budget-blocks-today",
      type: "exceeded",
      message: `${budgetInfo.blocksToday} provider call(s) were blocked today by token or cost budgets.`,
      timestamp: ts,
      acknowledged: false,
    });
  }
  const pct = budgetInfo.percentage;
  if (pct >= settings.critical_threshold) {
    out.push({
      id: "budget-pct-critical",
      type: "critical",
      message: `Daily token usage is at ${pct.toFixed(0)}% of the daily cap (warning at ${settings.warning_threshold}%, critical at ${settings.critical_threshold}%).`,
      timestamp: ts,
      acknowledged: false,
    });
  } else if (pct >= settings.warning_threshold) {
    out.push({
      id: "budget-pct-warning",
      type: "warning",
      message: `Daily token usage is at ${pct.toFixed(0)}% of the daily cap.`,
      timestamp: ts,
      acknowledged: false,
    });
  }
  return out;
}

export function buildUsageForecast(
  records: UsageRecord[],
  summary: ProviderUsageSummary,
  monthlyLimit: number,
): UsageForecast {
  const current = Number(summary.tokens_sent_today ?? 0);
  const byDay = rollupUsageByDay(records);
  const tokenSum = byDay.reduce((s, r) => s + r.tokens, 0);
  const dayCount = Math.max(1, byDay.length);
  const avgDaily = tokenSum / dayCount;
  const now = new Date();
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const daysRemaining = Math.max(1, end.getDate() - now.getDate() + 1);
  const projected = Math.round(current + avgDaily * Math.max(0, daysRemaining - 1));
  const costToday = Number(summary.cost_estimate_usd_today ?? 0);
  const projectedCost = current > 0 ? costToday * (projected / current) : costToday;
  const recommended_daily_cap =
    daysRemaining > 0 ? Math.max(0, Math.round((monthlyLimit - current) / daysRemaining)) : 0;
  return {
    projected_total: projected,
    projected_cost: Math.round(projectedCost * 1_000_000) / 1_000_000,
    days_remaining: daysRemaining,
    estimated_daily_average: Math.round(avgDaily),
    recommended_daily_cap: recommended_daily_cap,
  };
}

export function readAcknowledgedAlertIds(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(LS_ALERT_ACK);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as string[];
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

export function acknowledgeBudgetAlert(alertId: string): void {
  if (typeof window === "undefined") return;
  const s = readAcknowledgedAlertIds();
  s.add(alertId);
  window.localStorage.setItem(LS_ALERT_ACK, JSON.stringify(Array.from(s)));
}

export function filterAlertsByAcknowledgements(alerts: BudgetAlert[]): BudgetAlert[] {
  const ack = readAcknowledgedAlertIds();
  return alerts.map((a) => ({ ...a, acknowledged: ack.has(a.id) }));
}

export function buildDailyUsageBars(rolledUp: UsageRecord[], maxDays = 7): { date: string; label: string; tokens: number; cost: number }[] {
  const tail = rolledUp.slice(-maxDays);
  return tail.map((r) => {
    const d = new Date(r.date);
    const label = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
    return { date: r.date.slice(0, 10), label, tokens: r.tokens, cost: r.cost };
  });
}

export async function loadBudgetDashboardData(dailyCap = DEFAULT_DAILY_TOKEN_CAP): Promise<BudgetDashboardData> {
  let usage: ProviderUsageResponse = { calls: [], summary: {} };
  let prefs: UserBudgetPreferences | null = null;
  let loadError: string | undefined;
  try {
    usage = await fetchProviderUsage();
  } catch (e) {
    loadError = e instanceof Error ? e.message : String(e);
    usage = { calls: [], summary: {} };
  }
  try {
    prefs = await fetchUserBudgetPreferences();
  } catch {
    prefs = null;
  }

  const budgetInfo = budgetInfoFromSummary(usage.summary, dailyCap);
  const rawRecords = callsToUsageRecords(usage.calls || [], usage.summary || {});
  const byDay = rollupUsageByDay(rawRecords);
  const usageHistory = byDay.slice(-30);
  const providerBreakdown = buildProviderBreakdown(rawRecords);
  const memberUsage = providersToMemberUsage(providerBreakdown);
  const settings = buildBudgetSettings(usage.summary || {}, prefs, dailyCap);
  const forecast = buildUsageForecast(rawRecords, usage.summary || {}, settings.monthly_limit);
  const alerts = filterAlertsByAcknowledgements(buildBudgetAlerts(budgetInfo, settings));
  const dailyBars = buildDailyUsageBars(byDay, 7);

  return {
    usageHistory,
    dailyBars,
    providerBreakdown,
    memberUsage,
    alerts,
    settings,
    forecast,
    budgetInfo,
    loadError,
  };
}

/** Spec-shaped helpers (delegates to dashboard builder fields). */
export async function getUsageHistory(days = 30): Promise<UsageRecord[]> {
  const d = await loadBudgetDashboardData();
  return d.usageHistory.slice(-days);
}

export async function getProviderBreakdown(): Promise<ProviderUsage[]> {
  const d = await loadBudgetDashboardData();
  return d.providerBreakdown;
}

export async function getMemberUsage(): Promise<MemberUsage[]> {
  const d = await loadBudgetDashboardData();
  return d.memberUsage;
}

export async function getBudgetAlerts(): Promise<BudgetAlert[]> {
  const d = await loadBudgetDashboardData();
  return d.alerts;
}

export async function getBudgetSettings(): Promise<BudgetSettings> {
  const d = await loadBudgetDashboardData();
  return d.settings;
}

export async function getUsageForecast(): Promise<UsageForecast> {
  const d = await loadBudgetDashboardData();
  return d.forecast;
}

export async function updateBudgetSettings(updates: Partial<BudgetSettings>): Promise<void> {
  const ui: Record<string, unknown> = {};
  if (updates.monthly_limit != null) ui.monthly_token_target = Math.round(updates.monthly_limit);
  if (updates.warning_threshold != null) ui.budget_warning_threshold_pct = updates.warning_threshold;
  if (updates.critical_threshold != null) ui.budget_critical_threshold_pct = updates.critical_threshold;
  if (updates.alerts_enabled != null) ui.budget_alerts_enabled = updates.alerts_enabled;
  if (Object.keys(ui).length === 0) return;
  await patchUserBudgetSettings({ ui_preferences: ui });
}
