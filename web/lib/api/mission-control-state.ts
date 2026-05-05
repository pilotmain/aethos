import type { AttentionActivityItem } from "@/types/mission-control";

import { apiFetch } from "@/lib/api/client";

export type MissionControlStatePayload = Record<string, unknown>;

const CACHE_TTL_MS = 30_000;

let stateCache: { data: MissionControlStatePayload | null; hours: number; at: number } | null = null;

/** Invalidate cached GET /mission-control/state (call after mutations that affect dashboard lists). */
export function clearMissionControlStateCache(): void {
  stateCache = null;
}

/** GET /api/v1/mission-control/state — unified execution + dashboard payload (short TTL in-memory cache). */
export async function fetchMissionControlState(hours = 48): Promise<MissionControlStatePayload | null> {
  const now = Date.now();
  if (
    stateCache &&
    stateCache.hours === hours &&
    now - stateCache.at < CACHE_TTL_MS &&
    stateCache.data !== null
  ) {
    return stateCache.data;
  }

  try {
    const data = await apiFetch<MissionControlStatePayload>(`/mission-control/state?hours=${hours}`);
    stateCache = { data, hours, at: Date.now() };
    return data;
  } catch {
    return null;
  }
}

export function projectMetricsFromState(state: MissionControlStatePayload | null): {
  total: number;
  active: number;
} {
  const missions = state && Array.isArray(state.missions) ? state.missions : [];
  const total = missions.length;
  const terminal = new Set(["completed", "cancelled", "failed"]);
  const active = missions.filter((m) => {
    const st = String((m as { status?: string }).status || "").toLowerCase();
    return !terminal.has(st);
  }).length;
  return { total, active };
}

export function attentionFeedFromState(
  state: MissionControlStatePayload | null,
  limit = 8,
): AttentionActivityItem[] {
  const att = state && Array.isArray(state.attention) ? state.attention : [];
  return att.slice(0, limit).map((it) => {
    const o = it as Record<string, unknown>;
    return {
      id: String(o.id ?? ""),
      type: String(o.type ?? "item"),
      title: String(o.title ?? "Attention item"),
      description: typeof o.description === "string" ? o.description : undefined,
      created_at: typeof o.created_at === "string" ? o.created_at : undefined,
    };
  });
}

export function healthFlagsFromState(state: MissionControlStatePayload | null): {
  cron: boolean;
  providers: boolean;
} {
  const sched = state && Array.isArray(state.scheduler_jobs) ? state.scheduler_jobs : [];
  const cron = sched.some((j) => Boolean((j as { enabled?: boolean }).enabled));
  const rt = state?.runtime as Record<string, unknown> | undefined;
  const offline = Boolean(rt?.offline_mode);
  const remote = Boolean(rt?.remote_providers_available);
  return { cron, providers: remote && !offline };
}
