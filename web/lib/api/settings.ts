import type { SystemConfig } from "@/types/mission-control";

import { apiFetch } from "@/lib/api/client";

export type UserSettingsDocument = {
  privacy_mode?: string;
  ui_preferences?: Record<string, unknown>;
  identity?: Record<string, unknown>;
  token_budget_per_request?: number | null;
  daily_cost_budget_usd?: number | null;
  show_payload_summary?: boolean | null;
  allow_large_context?: boolean | null;
};

const ADV_KEY = "advanced_system";
const DEFAULT_SYSTEM: SystemConfig = {
  workspace_root: "",
  sandbox_mode: false,
  network_policy_strict: false,
  approvals_enabled: true,
  autonomous_mode: false,
  log_level: "info",
  data_dir: "",
};

function asBool(v: unknown, fallback: boolean): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function asLogLevel(v: unknown): SystemConfig["log_level"] {
  const s = String(v || "").toLowerCase();
  if (s === "debug" || s === "info" || s === "warning" || s === "error") return s;
  return "info";
}

export function systemConfigFromUserSettings(doc: UserSettingsDocument | null): SystemConfig {
  const ui = (doc?.ui_preferences || {}) as Record<string, unknown>;
  const adv = (ui[ADV_KEY] || {}) as Record<string, unknown>;
  return {
    workspace_root: typeof adv.workspace_root === "string" ? adv.workspace_root : DEFAULT_SYSTEM.workspace_root,
    sandbox_mode: asBool(adv.sandbox_mode, DEFAULT_SYSTEM.sandbox_mode),
    network_policy_strict: asBool(adv.network_policy_strict, DEFAULT_SYSTEM.network_policy_strict),
    approvals_enabled: asBool(adv.approvals_enabled, DEFAULT_SYSTEM.approvals_enabled),
    autonomous_mode: asBool(adv.autonomous_mode, DEFAULT_SYSTEM.autonomous_mode),
    log_level: asLogLevel(adv.log_level),
    data_dir: typeof adv.data_dir === "string" ? adv.data_dir : DEFAULT_SYSTEM.data_dir,
  };
}

export async function fetchUserSettingsDocument(): Promise<UserSettingsDocument> {
  return apiFetch<UserSettingsDocument>("/user/settings");
}

export async function postUserSettingsDocument(payload: Record<string, unknown>): Promise<UserSettingsDocument> {
  return apiFetch<UserSettingsDocument>("/user/settings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getSystemConfig(): Promise<SystemConfig> {
  try {
    const doc = await fetchUserSettingsDocument();
    return systemConfigFromUserSettings(doc);
  } catch {
    return { ...DEFAULT_SYSTEM };
  }
}

export async function saveSystemConfig(patch: Partial<SystemConfig>): Promise<SystemConfig> {
  const doc = await fetchUserSettingsDocument();
  const ui = { ...(doc.ui_preferences || {}) };
  const prev = (ui[ADV_KEY] || {}) as Record<string, unknown>;
  const next = { ...prev, ...patch };
  ui[ADV_KEY] = next;
  const out = await postUserSettingsDocument({ ui_preferences: ui });
  return systemConfigFromUserSettings(out);
}

/** Clear Mission Control “advanced” UI preferences (soft reset; does not delete API keys). */
export async function resetAdvancedUiPreferences(): Promise<void> {
  const doc = await fetchUserSettingsDocument();
  const ui = { ...(doc.ui_preferences || {}) };
  delete ui[ADV_KEY];
  delete ui.integrations_ui;
  delete ui.llm_default_models;
  delete ui.ollama_base_url;
  await postUserSettingsDocument({ ui_preferences: ui });
}

export async function exportSettingsSnapshot(): Promise<Record<string, unknown>> {
  const doc = await fetchUserSettingsDocument();
  const { identity: _i, ...rest } = doc;
  return {
    ...rest,
    exported_at: new Date().toISOString(),
    note: "Snapshot excludes secrets. API keys are not exportable from the browser.",
  };
}

export async function importSettingsSnapshot(payload: Record<string, unknown>): Promise<void> {
  const ui = payload.ui_preferences;
  if (ui && typeof ui === "object") {
    await postUserSettingsDocument({
      ui_preferences: ui as Record<string, unknown>,
      privacy_mode: typeof payload.privacy_mode === "string" ? payload.privacy_mode : undefined,
    });
    return;
  }
  throw new Error("Import file must include a ui_preferences object (from a prior export).");
}
