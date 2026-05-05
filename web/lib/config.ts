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

export function readConfig(): AethosWebConfig {
  if (typeof window === "undefined") {
    return { ...defaultConfig };
  }
  const raw =
    window.localStorage.getItem(WEB_CONFIG_STORAGE_KEY) ||
    window.localStorage.getItem(WEB_CONFIG_LEGACY_STORAGE_KEY);
  if (!raw) {
    return { ...defaultConfig };
  }
  try {
    const j = JSON.parse(raw) as Partial<AethosWebConfigStored>;
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
