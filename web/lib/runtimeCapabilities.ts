import { apiFetch } from "@/lib/api/client";

export type RuntimeCapabilities = {
  mc_compatibility_version?: string;
  available_routes?: { method?: string; path?: string }[];
  feature_flags?: Record<string, boolean>;
};

let cache: RuntimeCapabilities | null = null;
let cacheAt = 0;
const TTL_MS = 60_000;

export async function fetchRuntimeCapabilities(): Promise<RuntimeCapabilities> {
  if (cache && Date.now() - cacheAt < TTL_MS) {
    return cache;
  }
  try {
    const caps = await apiFetch<RuntimeCapabilities>("/runtime/capabilities");
    cache = caps;
    cacheAt = Date.now();
    return caps;
  } catch {
    return cache ?? {};
  }
}

export function routeAvailable(caps: RuntimeCapabilities, path: string): boolean {
  const routes = caps.available_routes ?? [];
  return routes.some((r) => r.path === path);
}

export async function fetchIfRouteAvailable<T>(
  path: string,
  fallback: T,
): Promise<{ data: T; unavailable: boolean }> {
  const caps = await fetchRuntimeCapabilities();
  const full = path.startsWith("/api/v1") ? path : `/api/v1${path.startsWith("/") ? "" : "/"}${path}`;
  if (!routeAvailable(caps, full) && (caps.available_routes?.length ?? 0) > 0) {
    return { data: fallback, unavailable: true };
  }
  try {
    const data = await apiFetch<T>(path);
    return { data, unavailable: false };
  } catch {
    return { data: fallback, unavailable: true };
  }
}
