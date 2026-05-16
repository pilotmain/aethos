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
      return `AethOS runtime hit an internal error while loading this panel. Other panels may still be available.`;
    }
    if (code === "404") {
      return `This feature is not available in the current AethOS runtime configuration.`;
    }
    return m;
  }
  if (/Cannot reach API/i.test(m)) {
    return "AethOS runtime connection is not available yet. The API may still be starting, or connection settings may need repair.";
  }
  if (/unknown provider/i.test(m)) {
    return "This provider is not available in the current AethOS runtime configuration.";
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
  if (stale || status === "stale")
    return "AethOS runtime is reconnecting. Cached operational truth remains available.";
  if (status === "degraded")
    return "AethOS runtime is reconnecting. Operational continuity is being restored.";
  if (status === "partial")
    return "Some panels are partial — summaries and recovery remain available.";
  if (status === "recovering") return "AethOS is recovering — orchestrator summaries stay online.";
  if (status === "offline") return "API offline — check Connection settings when convenient.";
  return "Operational status degraded — review Runtime recovery for detail.";
}
