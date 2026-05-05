import type { LLMProviderConfig } from "@/types/mission-control";

import { apiFetch } from "@/lib/api/client";
import { fetchUserSettingsDocument, postUserSettingsDocument } from "@/lib/api/settings";
import { fetchHealth } from "@/lib/api/health";
import { fetchSystemHealth } from "@/lib/api/system";

export type WebByokKeyRow = {
  provider: string;
  has_key: boolean;
  last4: string;
};

export type LLMProviderRow = LLMProviderConfig & { api_key_set: boolean; id: LLMProviderConfig["name"] };

const MODELS_KEY = "llm_default_models";
const OLLAMA_URL_KEY = "ollama_base_url";

export async function fetchWebKeys(): Promise<WebByokKeyRow[]> {
  const rows = await apiFetch<WebByokKeyRow[]>("/web/keys");
  return Array.isArray(rows) ? rows : [];
}

export async function setWebProviderKey(provider: "openai" | "anthropic", key: string): Promise<WebByokKeyRow> {
  return apiFetch<WebByokKeyRow>("/web/keys", {
    method: "POST",
    body: JSON.stringify({ provider, key }),
  });
}

export async function deleteWebProviderKey(provider: "openai" | "anthropic"): Promise<void> {
  await apiFetch<Record<string, string>>(`/web/keys/${encodeURIComponent(provider)}`, { method: "DELETE" });
}

function readModelPrefs(ui: Record<string, unknown>): Record<string, string> {
  const raw = ui[MODELS_KEY];
  if (!raw || typeof raw !== "object") return {};
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof v === "string" && v.trim()) out[k] = v.trim();
  }
  return out;
}

async function saveModelPrefs(models: Record<string, string>): Promise<void> {
  const doc = await fetchUserSettingsDocument();
  const ui = { ...(doc.ui_preferences || {}) };
  ui[MODELS_KEY] = models;
  await postUserSettingsDocument({ ui_preferences: ui });
}

export async function getLLMProviders(): Promise<LLMProviderRow[]> {
  const [keys, health, doc, shallow] = await Promise.all([
    fetchWebKeys().catch(() => [] as WebByokKeyRow[]),
    fetchSystemHealth().catch(() => null),
    fetchUserSettingsDocument().catch(() => null),
    fetchHealth().catch(() => ({ ok: false })),
  ]);

  const ui = (doc?.ui_preferences || {}) as Record<string, unknown>;
  const models = readModelPrefs(ui);
  const ollamaBase =
    typeof ui[OLLAMA_URL_KEY] === "string" ? (ui[OLLAMA_URL_KEY] as string) : undefined;
  const tags = new Set((health?.provider_tags || []).map((t) => String(t).toLowerCase()));
  const remoteReady = Boolean(shallow.ok && health?.ok);
  const last = new Date().toISOString();

  const row = (
    name: LLMProviderConfig["name"],
    overrides: Partial<LLMProviderRow>,
  ): LLMProviderRow => {
    const base: LLMProviderRow = {
      id: name,
      name,
      configured: false,
      model: models[name],
      status: "unknown",
      api_key_set: false,
      last_check: last,
      ...overrides,
    };
    return base;
  };

  const openaiKey = keys.find((k) => k.provider === "openai");
  const anthropicKey = keys.find((k) => k.provider === "anthropic");

  const openai: LLMProviderRow = row("openai", {
    api_key_set: Boolean(openaiKey?.has_key),
    configured: Boolean(openaiKey?.has_key || tags.has("openai")),
    model: models.openai,
    status:
      openaiKey?.has_key && remoteReady ? "connected" : tags.has("openai") && remoteReady ? "connected" : "disconnected",
  });

  const anthropic: LLMProviderRow = row("anthropic", {
    api_key_set: Boolean(anthropicKey?.has_key),
    configured: Boolean(anthropicKey?.has_key || tags.has("anthropic")),
    model: models.anthropic,
    status:
      anthropicKey?.has_key && remoteReady
        ? "connected"
        : tags.has("anthropic") && remoteReady
          ? "connected"
          : "disconnected",
  });

  const deepseekConfigured = Boolean(models.deepseek) || String(health?.providers || "") === "ready";
  const deepseek: LLMProviderRow = row("deepseek", {
    configured: deepseekConfigured,
    model: models.deepseek,
    status: deepseekConfigured && remoteReady ? "connected" : remoteReady ? "unknown" : "disconnected",
  });

  const ollamaConfigured = Boolean(models.ollama || ollamaBase);
  const ollama: LLMProviderRow = row("ollama", {
    configured: ollamaConfigured,
    model: models.ollama,
    base_url: ollamaBase,
    status: ollamaConfigured && remoteReady && !health?.offline_mode ? "connected" : remoteReady ? "unknown" : "disconnected",
  });

  return [openai, anthropic, deepseek, ollama];
}

/**
 * There is no POST /providers/test in the API. We approximate:
 * - openai/anthropic: shallow health + BYOK row present
 * - deepseek/ollama: process health only (keys live in server env / Ollama host).
 */
export async function testLLMProvider(providerId: string): Promise<boolean> {
  const [shallow, health, keys] = await Promise.all([
    fetchHealth(),
    fetchSystemHealth().catch(() => null),
    fetchWebKeys().catch(() => []),
  ]);
  if (!shallow.ok) return false;
  const id = providerId.toLowerCase();
  if (id === "openai") return Boolean(keys.find((k) => k.provider === "openai")?.has_key) && Boolean(health?.ok);
  if (id === "anthropic") return Boolean(keys.find((k) => k.provider === "anthropic")?.has_key) && Boolean(health?.ok);
  return Boolean(health?.ok);
}

export async function saveLLMProvider(
  providerId: string,
  apiKey: string,
  model?: string,
  ollamaBaseUrl?: string,
): Promise<void> {
  const id = providerId.toLowerCase() as LLMProviderConfig["name"];
  const doc = await fetchUserSettingsDocument();
  const ui = { ...(doc.ui_preferences || {}) };
  const models = readModelPrefs(ui);

  if (model !== undefined) {
    const m = String(model).trim();
    if (m) models[id] = m;
    else delete models[id];
  }

  if (id === "openai" || id === "anthropic") {
    if (apiKey.trim()) {
      await setWebProviderKey(id, apiKey.trim());
    }
  }

  if (id === "ollama" && ollamaBaseUrl != null) {
    ui[OLLAMA_URL_KEY] = ollamaBaseUrl.trim() || null;
  }

  ui[MODELS_KEY] = models;
  await postUserSettingsDocument({ ui_preferences: ui });
}

export async function removeLLMProviderKey(providerId: "openai" | "anthropic"): Promise<void> {
  await deleteWebProviderKey(providerId);
}
