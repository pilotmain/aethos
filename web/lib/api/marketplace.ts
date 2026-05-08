/**
 * Phase 71 — Mission Control "Marketplace" client.
 *
 * Wraps the web-auth proxy under ``/api/v1/marketplace/*``:
 *   - GET  /marketplace/search?q=&limit=
 *   - GET  /marketplace/popular?limit=
 *   - GET  /marketplace/skill/{name}
 *   - GET  /marketplace/installed
 *   - POST /marketplace/install                 (owner-only)
 *   - POST /marketplace/uninstall/{name}        (owner-only)
 *   - POST /marketplace/update/{name}?force=    (owner-only)
 *
 * The ClawHub backend itself (under ``/api/v1/clawhub/*``) keeps the cron-token
 * gate for automation; this proxy gives the browser a parallel surface that
 * uses standard web auth (``X-User-Id`` plus optional ``Authorization: Bearer``).
 */

import { apiFetch } from "@/lib/api/client";

export type MarketplaceSkillInfo = {
  name: string;
  version: string;
  description: string;
  author: string;
  publisher: string;
  tags: string[];
  downloads: number;
  rating: number;
  updated_at: string;
  signature: string | null;
  manifest_url: string;
  archive_url: string;
};

export type InstalledSkillRow = {
  name: string;
  version: string;
  source: string;
  installed_at: string;
  updated_at: string;
  status: string;
  pinned_version: string | null;
  publisher: string | null;
  source_url: string | null;
};

export type MarketplaceSkillsResponse = {
  ok: boolean;
  skills: MarketplaceSkillInfo[];
};

export type InstalledSkillsResponse = {
  ok: boolean;
  skills: InstalledSkillRow[];
};

export type MarketplaceMutationResponse = {
  ok: boolean;
  message: string;
  skill_name?: string | null;
};

export async function searchSkills(
  query: string,
  limit = 20,
): Promise<MarketplaceSkillInfo[]> {
  const q = (query || "").trim();
  if (!q) return [];
  const safe = Math.max(1, Math.min(Math.trunc(limit) || 20, 100));
  const data = await apiFetch<MarketplaceSkillsResponse>(
    `/marketplace/search?q=${encodeURIComponent(q)}&limit=${safe}`,
  );
  return Array.isArray(data?.skills) ? data.skills : [];
}

export async function popularSkills(limit = 20): Promise<MarketplaceSkillInfo[]> {
  const safe = Math.max(1, Math.min(Math.trunc(limit) || 20, 100));
  const data = await apiFetch<MarketplaceSkillsResponse>(
    `/marketplace/popular?limit=${safe}`,
  );
  return Array.isArray(data?.skills) ? data.skills : [];
}

export async function getSkillInfo(name: string): Promise<MarketplaceSkillInfo | null> {
  const nm = (name || "").trim();
  if (!nm) return null;
  try {
    const data = await apiFetch<{ ok: boolean; skill: MarketplaceSkillInfo }>(
      `/marketplace/skill/${encodeURIComponent(nm)}`,
    );
    return data?.skill ?? null;
  } catch {
    return null;
  }
}

export async function listInstalledSkills(): Promise<InstalledSkillRow[]> {
  const data = await apiFetch<InstalledSkillsResponse>(`/marketplace/installed`);
  return Array.isArray(data?.skills) ? data.skills : [];
}

export async function installSkill(
  name: string,
  version = "latest",
  force = false,
): Promise<MarketplaceMutationResponse> {
  return apiFetch<MarketplaceMutationResponse>(`/marketplace/install`, {
    method: "POST",
    body: JSON.stringify({ name, version, force }),
  });
}

export async function uninstallSkill(name: string): Promise<MarketplaceMutationResponse> {
  return apiFetch<MarketplaceMutationResponse>(
    `/marketplace/uninstall/${encodeURIComponent(name)}`,
    { method: "POST" },
  );
}

export async function updateSkill(
  name: string,
  force = false,
): Promise<MarketplaceMutationResponse> {
  const qs = force ? `?force=true` : "";
  return apiFetch<MarketplaceMutationResponse>(
    `/marketplace/update/${encodeURIComponent(name)}${qs}`,
    { method: "POST" },
  );
}
