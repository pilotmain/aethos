import type { IntegrationConfig } from "@/types/mission-control";

import { apiFetch } from "@/lib/api/client";
import { fetchUserSettingsDocument, postUserSettingsDocument } from "@/lib/api/settings";
const KEY = "integrations_ui";

type IntegrationUiRow = {
  enabled?: boolean;
  webhook_url?: string;
  channel?: string;
  token?: string;
  repository?: string;
  last_active?: string;
};

function readMap(doc: { ui_preferences?: Record<string, unknown> } | null): Record<string, IntegrationUiRow> {
  const ui = (doc?.ui_preferences || {}) as Record<string, unknown>;
  const raw = ui[KEY];
  if (!raw || typeof raw !== "object") return {};
  const out: Record<string, IntegrationUiRow> = {};
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (v && typeof v === "object") out[k] = v as IntegrationUiRow;
  }
  return out;
}

async function writeMap(map: Record<string, IntegrationUiRow>): Promise<void> {
  const doc = await fetchUserSettingsDocument();
  const ui = { ...(doc.ui_preferences || {}) };
  ui[KEY] = map;
  await postUserSettingsDocument({ ui_preferences: ui });
}

const DEFAULTS: IntegrationConfig[] = [
  { id: "slack", name: "Slack", type: "slack", enabled: false, configured: false },
  { id: "github", name: "GitHub", type: "github", enabled: false, configured: false },
  { id: "telegram", name: "Telegram", type: "telegram", enabled: false, configured: false },
  { id: "discord", name: "Discord", type: "discord", enabled: false, configured: false },
];

export async function getIntegrations(): Promise<IntegrationConfig[]> {
  const doc = await fetchUserSettingsDocument().catch(() => null);
  const map = readMap(doc);
  return DEFAULTS.map((d) => {
    const row = map[d.id] || {};
    const webhook_url = row.webhook_url;
    const repository = typeof row.repository === "string" ? row.repository : "";
    const channelField = d.type === "github" ? repository : row.channel;
    const configured =
      d.type === "slack"
        ? Boolean((webhook_url || "").trim())
        : d.type === "github"
          ? Boolean((row.token || "").trim() && repository.trim())
          : Boolean((row.token || "").trim() || (webhook_url || "").trim());
    return {
      ...d,
      enabled: row.enabled ?? false,
      configured,
      webhook_url: webhook_url || undefined,
      channel: channelField || undefined,
      last_active: row.last_active,
    };
  });
}

export async function toggleIntegration(id: string, enabled: boolean): Promise<void> {
  const doc = await fetchUserSettingsDocument();
  const map = readMap(doc);
  map[id] = { ...(map[id] || {}), enabled };
  await writeMap(map);
}

export async function saveIntegration(id: string, patch: Partial<IntegrationConfig>): Promise<void> {
  await saveIntegrationFields(id, {
    webhook_url: patch.webhook_url,
    channel: patch.channel,
    enabled: patch.enabled,
  });
}

export async function saveIntegrationFields(
  id: string,
  fields: {
    enabled?: boolean;
    webhook_url?: string;
    channel?: string;
    repository?: string;
    token?: string;
  },
): Promise<void> {
  const doc = await fetchUserSettingsDocument();
  const map = readMap(doc);
  const prev = map[id] || {};
  const next: IntegrationUiRow = { ...prev };
  if (fields.enabled !== undefined) next.enabled = fields.enabled;
  if (fields.webhook_url !== undefined) next.webhook_url = fields.webhook_url;
  if (fields.channel !== undefined) next.channel = fields.channel;
  if (fields.repository !== undefined) next.repository = fields.repository;
  if (fields.token !== undefined) next.token = fields.token;
  next.last_active = new Date().toISOString();
  map[id] = next;
  await writeMap(map);
}

export async function removeIntegration(id: string): Promise<void> {
  const doc = await fetchUserSettingsDocument();
  const map = readMap(doc);
  delete map[id];
  await writeMap(map);
}
