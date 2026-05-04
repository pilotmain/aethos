export type NexaWebConfig = {
  apiBase: string;
  userId: string;
  token: string;
};

/** Persisted shape includes schema metadata (v2). */
export type NexaWebConfigStored = NexaWebConfig & {
  schemaVersion?: number;
  savedAt?: string;
};

const KEY = "nexa_web_v1";
const CONFIG_SCHEMA_VERSION = 2;

/**
 * Default API origin for the browser. Docker publishes the API on host **8010** → container 8000
 * (avoids sticky cache / conflicts with other services on :8000). Override at build time:
 * `NEXT_PUBLIC_NEXA_API_BASE=http://127.0.0.1:9000`.
 */
export const DEFAULT_API_BASE =
  typeof process !== "undefined" &&
  typeof process.env.NEXT_PUBLIC_NEXA_API_BASE === "string" &&
  process.env.NEXT_PUBLIC_NEXA_API_BASE.trim()
    ? process.env.NEXT_PUBLIC_NEXA_API_BASE.trim().replace(/\/$/, "")
    : "http://127.0.0.1:8010";

export const defaultConfig: NexaWebConfig = {
  apiBase: DEFAULT_API_BASE,
  userId: "",
  token: "",
};

/** One-time migration when Docker moved published API port 8000 → 8010 on host. */
function migrateStoredApiBase(raw: string | undefined): string {
  const s = (raw || "").trim().replace(/\/$/, "");
  if (
    s === "http://127.0.0.1:8000" ||
    s === "http://localhost:8000" ||
    s === "http://127.0.0.1:8000/" ||
    s === "http://localhost:8000/"
  ) {
    return DEFAULT_API_BASE;
  }
  return raw?.trim() ? raw.trim().replace(/\/$/, "") : "";
}

export function readConfig(): NexaWebConfig {
  if (typeof window === "undefined") {
    return { ...defaultConfig };
  }
  const raw = window.localStorage.getItem(KEY);
  if (!raw) {
    return { ...defaultConfig };
  }
  try {
    const j = JSON.parse(raw) as Partial<NexaWebConfigStored>;
    const apiBase = migrateStoredApiBase(j.apiBase) || DEFAULT_API_BASE;
    return {
      apiBase,
      userId: j.userId || "",
      token: j.token || "",
    };
  } catch {
    return { ...defaultConfig };
  }
}

export function saveConfig(c: NexaWebConfig): void {
  if (typeof window === "undefined") {
    return;
  }
  const payload: NexaWebConfigStored = {
    schemaVersion: CONFIG_SCHEMA_VERSION,
    savedAt: new Date().toISOString(),
    apiBase: c.apiBase.trim() || DEFAULT_API_BASE,
    userId: c.userId.trim(),
    token: c.token.trim(),
  };
  window.localStorage.setItem(KEY, JSON.stringify(payload));
}

/** Point the browser at a working API origin and reload (e.g. 8120 → 8010). */
export function applyApiBaseAndReload(nextApiBase: string): void {
  if (typeof window === "undefined") {
    return;
  }
  const c = readConfig();
  saveConfig({
    ...c,
    apiBase: nextApiBase.trim().replace(/\/$/, "") || DEFAULT_API_BASE,
  });
  window.location.reload();
}

export function isConfigured(): boolean {
  const c = readConfig();
  return Boolean(c.userId);
}
