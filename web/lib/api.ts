import { clearSavedBearerToken, DEFAULT_API_BASE, readConfig } from "./config";
import type { TrustActivityResponse, TrustSummaryResponse, WebReleaseNotes } from "./aethos-types";

const API_PREFIX = "/api/v1";

export interface ApiOptions extends RequestInit {
  requireAuth?: boolean;
}

function parseErrorBodyText(t: string): string {
  let detail = t;
  try {
    const j = JSON.parse(t) as { detail?: string | { msg?: string }[] };
    if (j.detail) {
      if (typeof j.detail === "string") {
        return j.detail;
      }
      if (Array.isArray(j.detail) && j.detail[0] && typeof j.detail[0] === "object") {
        const m = (j.detail[0] as { msg?: string }).msg;
        if (m) return m;
      }
      if (Array.isArray(j.detail) && typeof j.detail[0] === "string") {
        return j.detail[0];
      }
    }
  } catch {
    /* not JSON */
  }
  return detail;
}

/** Friendlier message for Mission Control surfaces (auth hints). */
export function formatMissionControlApiError(message: string): string {
  const m = message.trim();
  if (/^401\b/.test(m) || /^403\b/.test(m) || m.includes("Unauthorized")) {
    return `${m} — Open Login / Connection and set X-User-Id (and bearer token if your API requires NEXA_WEB_API_TOKEN).`;
  }
  if (/Cannot reach API/i.test(m)) {
    return `${m} Use Retry after fixing API base URL or starting the Nexa API.`;
  }
  return m;
}

function url(path: string): string {
  const c = readConfig();
  const base = (c.apiBase || DEFAULT_API_BASE).replace(/\/$/, "");
  return `${base}${API_PREFIX}${path.startsWith("/") ? path : `/${path}`}`;
}

function configuredHeaders(requireAuth = true): Record<string, string> {
  const c = readConfig();
  const h: Record<string, string> = {};
  const userId = c.userId.trim();
  const token = c.token.trim();
  if (userId) {
    h["X-User-Id"] = userId;
  }
  if (requireAuth && token) {
    h.Authorization = `Bearer ${token}`;
  }
  return h;
}

function headersToRecord(headers?: HeadersInit): Record<string, string> {
  if (!headers) {
    return {};
  }
  if (typeof Headers !== "undefined" && headers instanceof Headers) {
    const out: Record<string, string> = {};
    headers.forEach((value, key) => {
      out[key] = value;
    });
    return out;
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return headers as Record<string, string>;
}

/** Maps browser "Failed to fetch" to a message that names API base / CORS / port. */
async function fetchOrNetworkHint(urlStr: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(urlStr, init);
  } catch (e) {
    if (e instanceof TypeError) {
      const origin =
        typeof window !== "undefined" ? window.location.origin : "(browser origin)";
      throw new Error(
        `Cannot reach API (wrong URL/port, server down, or CORS). In Login → Connection, set API base to where /api/v1/health works (e.g. http://127.0.0.1:8120 if you use scripts/nexa_next_local_all.sh, or http://127.0.0.1:8010 with Docker). This page is ${origin}.`,
      );
    }
    throw e;
  }
}

export async function webFetch<T = unknown>(path: string, init: ApiOptions = {}): Promise<T> {
  const { requireAuth = true, headers: initHeaders, ...fetchInit } = init;
  const h = { ...configuredHeaders(requireAuth), ...headersToRecord(initHeaders) };
  if (init.body && !h["Content-Type"]) {
    h["Content-Type"] = "application/json";
  }
  if (!h["Accept"]) {
    h["Accept"] = "application/json";
  }

  const r = await fetchOrNetworkHint(url(path), { ...fetchInit, headers: h });
  const text = await r.text();
  if (r.status === 401) {
    const msg =
      parseErrorBodyText(text) || "Unauthorized (check X-User-Id and optional bearer token)";
    if (/bearer token|Authorization:\s*Bearer/i.test(msg)) {
      clearSavedBearerToken();
      if (typeof window !== "undefined") {
        window.localStorage.removeItem('aethos_bearer_token');
        window.localStorage.removeItem('aethos_web_v1');
      }
    }
    throw new Error(`Invalid bearer token. Please check your Connection settings. (${r.status}: ${msg})`);
  }
  if (!r.ok) {
    const msg = parseErrorBodyText(text) || r.statusText;
    throw new Error(`${r.status}: ${msg}`);
  }
  if (r.status === 204 || !text.trim()) {
    return null as T;
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error(
      text.length > 400 ? `${text.slice(0, 400)}…` : text || "Invalid JSON response from API"
    );
  }
}

/** No auth — public release highlights for banner / System tab. */
export async function fetchTrustActivity(hours: number, limit = 200): Promise<TrustActivityResponse> {
  const q = new URLSearchParams({
    hours: String(hours),
    limit: String(limit),
  });
  return webFetch<TrustActivityResponse>(`/trust/activity?${q}`);
}

export async function fetchTrustSummary(
  hours: number,
  recentLimit = 20
): Promise<TrustSummaryResponse> {
  const q = new URLSearchParams({
    hours: String(hours),
    recent_limit: String(recentLimit),
  });
  return webFetch<TrustSummaryResponse>(`/trust/summary?${q}`);
}

export async function webFetchPublicReleaseNotes(): Promise<WebReleaseNotes> {
  const c = readConfig();
  const base = (c.apiBase || DEFAULT_API_BASE).replace(/\/$/, "");
  const r = await fetchOrNetworkHint(`${base}${API_PREFIX}/web/release-notes`);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(parseErrorBodyText(t) || r.statusText);
  }
  return r.json() as Promise<WebReleaseNotes>;
}

export async function webDownloadBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const h = { ...configuredHeaders(true), ...headersToRecord(init.headers) };
  const r = await fetchOrNetworkHint(url(path), { ...init, headers: h, method: init.method || "GET" });
  if (r.status === 401) {
    const t = await r.text();
    const msg = parseErrorBodyText(t) || "Unauthorized (check X-User-Id and optional bearer token)";
    if (/bearer token|Authorization:\s*Bearer/i.test(msg)) {
      clearSavedBearerToken();
    }
    throw new Error(msg);
  }
  if (!r.ok) {
    const t = await r.text();
    throw new Error(parseErrorBodyText(t) || r.statusText);
  }
  return r.blob();
}

export function downloadBlobToFile(blob: Blob, filename: string): void {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.rel = "noopener";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 60_000);
}

export async function autoInitUser(chatId: string, username?: string): Promise<void> {
  const c = readConfig();
  const base = (c.apiBase || DEFAULT_API_BASE).replace(/\/$/, "");
  await fetch(`${base}${API_PREFIX}/users/auto-init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, username })
  });
}
