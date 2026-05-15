export type AethosWebConfig = {
  apiBase: string;
  userId: string;
  token: string;
};

export type AethosWebConfigStored = AethosWebConfig & {
  schemaVersion?: number;
  savedAt?: string;
};

/** @deprecated Prefer ``AethosWebConfig`` (Phase 36 rebrand). */
export type NexaWebConfig = AethosWebConfig;

/** @deprecated Prefer ``AethosWebConfigStored``. */
export type NexaWebConfigStored = AethosWebConfigStored;

/** Current localStorage key for Mission Control web config. */
export const WEB_CONFIG_STORAGE_KEY = "aethos_web_v1";

/** Legacy key — still read on load for migration; new saves use :data:`WEB_CONFIG_STORAGE_KEY`. */
export const WEB_CONFIG_LEGACY_STORAGE_KEY = "nexa_web_v1";

/** Standalone keys used by Connection settings and manual browser recovery flows. */
export const WEB_API_BASE_STORAGE_KEY = "aethos_api_base";
export const WEB_USER_ID_STORAGE_KEY = "aethos_user_id";
export const WEB_BEARER_TOKEN_STORAGE_KEY = "aethos_bearer_token";

const CONFIG_SCHEMA_VERSION = 2;

/**
 * Default API origin for the browser. Docker publishes the API on host **8010** → container 8000.
 * Override at build time: ``NEXT_PUBLIC_AETHOS_API_BASE`` (preferred) or legacy ``NEXT_PUBLIC_NEXA_API_BASE``.
 */
export const DEFAULT_API_BASE = (() => {
  if (typeof process === "undefined") {
    return "http://127.0.0.1:8010";
  }
  const a = process.env.NEXT_PUBLIC_AETHOS_API_BASE;
  if (typeof a === "string" && a.trim()) {
    return a.trim().replace(/\/$/, "");
  }
  const n = process.env.NEXT_PUBLIC_NEXA_API_BASE;
  if (typeof n === "string" && n.trim()) {
    return n.trim().replace(/\/$/, "");
  }
  return "http://127.0.0.1:8010";
})();

export const defaultConfig: AethosWebConfig = {
  apiBase: DEFAULT_API_BASE,
  userId: "",
  token: "",
};

/** Normalize stored API origin (trailing slash). Do not rewrite port 8000 — host installs use it. */
function migrateStoredApiBase(raw: string | undefined): string {
  return (raw || "").trim().replace(/\/$/, "");
}

function readStandaloneConfig(): Partial<AethosWebConfig> {
  if (typeof window === "undefined") {
    return {};
  }
  return {
    apiBase: migrateStoredApiBase(window.localStorage.getItem(WEB_API_BASE_STORAGE_KEY) || undefined),
    userId: window.localStorage.getItem(WEB_USER_ID_STORAGE_KEY)?.trim() || "",
    token: window.localStorage.getItem(WEB_BEARER_TOKEN_STORAGE_KEY)?.trim() || "",
  };
}

export function readConfig(): AethosWebConfig {
  if (typeof window === "undefined") {
    return { ...defaultConfig };
  }
  const standalone = readStandaloneConfig();
  const raw =
    window.localStorage.getItem(WEB_CONFIG_STORAGE_KEY) ||
    window.localStorage.getItem(WEB_CONFIG_LEGACY_STORAGE_KEY);
  if (!raw) {
    return {
      apiBase: standalone.apiBase || DEFAULT_API_BASE,
      userId: standalone.userId || "",
      token: standalone.token || "",
    };
  }
  try {
    const j = JSON.parse(raw) as Partial<AethosWebConfigStored>;
    const apiBase = migrateStoredApiBase(j.apiBase) || DEFAULT_API_BASE;
    return {
      apiBase: standalone.apiBase || apiBase,
      userId: standalone.userId || j.userId || "",
      token: standalone.token || j.token || "",
    };
  } catch {
    return {
      apiBase: standalone.apiBase || DEFAULT_API_BASE,
      userId: standalone.userId || "",
      token: standalone.token || "",
    };
  }
}

export function saveConfig(c: AethosWebConfig): void {
  if (typeof window === "undefined") {
    return;
  }
  const payload: AethosWebConfigStored = {
    schemaVersion: CONFIG_SCHEMA_VERSION,
    savedAt: new Date().toISOString(),
    apiBase: c.apiBase.trim() || DEFAULT_API_BASE,
    userId: c.userId.trim(),
    token: c.token.trim(),
  };
  window.localStorage.setItem(WEB_CONFIG_STORAGE_KEY, JSON.stringify(payload));
  window.localStorage.setItem(WEB_API_BASE_STORAGE_KEY, payload.apiBase);
  if (payload.userId) {
    window.localStorage.setItem(WEB_USER_ID_STORAGE_KEY, payload.userId);
  } else {
    window.localStorage.removeItem(WEB_USER_ID_STORAGE_KEY);
  }
  if (payload.token) {
    window.localStorage.setItem(WEB_BEARER_TOKEN_STORAGE_KEY, payload.token);
  } else {
    window.localStorage.removeItem(WEB_BEARER_TOKEN_STORAGE_KEY);
  }
}

export function clearSavedBearerToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  const c = readConfig();
  saveConfig({ ...c, token: "" });
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
