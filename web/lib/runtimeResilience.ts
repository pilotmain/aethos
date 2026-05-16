import { apiFetch } from "@/lib/api/client";
import { readConfig } from "@/lib/config";

export type OperationalStatus =
  | "healthy"
  | "degraded"
  | "recovering"
  | "partial"
  | "offline"
  | "stale";

export type ResilientFetchResult<T> = {
  data: T;
  status: OperationalStatus;
  error?: string;
  stale?: boolean;
};

const panelCache = new Map<string, { data: unknown; at: number }>();
const PANEL_TTL_MS = 30_000;

function cacheKey(path: string): string {
  const c = readConfig();
  return `${c.apiBase}|${c.userId}|${path}`;
}

function isApiHttpError(message: string): boolean {
  return /^\d{3}\b/.test(message.trim());
}

export function formatOperationalError(message: string): string {
  const m = message.trim();
  if (isApiHttpError(m)) {
    const code = m.split(":")[0];
    if (code === "500" || code === "502" || code === "503") {
      return `Runtime service error (${code}). Some panels may use cached data — not an API connection failure.`;
    }
    if (code === "404") {
      return `Feature unavailable (${code}). This endpoint may not be enabled on this API build.`;
    }
    return m;
  }
  if (/Cannot reach API/i.test(m)) {
    return m;
  }
  return m;
}

export async function fetchPanelResilient<T>(
  path: string,
  fallback: T,
): Promise<ResilientFetchResult<T>> {
  const key = cacheKey(path);
  const cached = panelCache.get(key);
  try {
    const data = await apiFetch<T>(path);
    panelCache.set(key, { data, at: Date.now() });
    return { data, status: "healthy" };
  } catch (e) {
    const message = e instanceof Error ? e.message : "Request failed";
    if (cached && Date.now() - cached.at < PANEL_TTL_MS * 4) {
      return {
        data: cached.data as T,
        status: "stale",
        error: formatOperationalError(message),
        stale: true,
      };
    }
    return {
      data: fallback,
      status: isApiHttpError(message) ? "degraded" : "partial",
      error: formatOperationalError(message),
    };
  }
}

export async function revalidateHealth(): Promise<boolean> {
  try {
    await apiFetch<{ status?: string }>("/health", { requireAuth: false });
    if (typeof window !== "undefined") {
      window.localStorage.setItem("aethos_last_health_ok", String(Date.now()));
    }
    return true;
  } catch {
    return false;
  }
}

export function operationalBanner(status: OperationalStatus, stale?: boolean): string | null {
  if (status === "healthy" && !stale) return null;
  if (stale || status === "stale") return "Using cached truth — hydration may be recovering.";
  if (status === "degraded") return "Runtime recovering — some panels show partial data.";
  if (status === "partial") return "Some operational panels unavailable.";
  if (status === "recovering") return "Runtime recovering.";
  if (status === "offline") return "API offline — check Connection settings.";
  return "Operational status degraded.";
}
