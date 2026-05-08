/**
 * Phase 71 + 75 — Mission Control "Marketplace" client.
 *
 * Wraps the web-auth proxy under ``/api/v1/marketplace/*``:
 *   - GET  /marketplace/search?q=&limit=&category=
 *   - GET  /marketplace/popular?limit=
 *   - GET  /marketplace/featured?limit=                 (75)
 *   - GET  /marketplace/categories                      (75)
 *   - GET  /marketplace/skill/{name}
 *   - GET  /marketplace/skill/{name}/details            (75)
 *   - GET  /marketplace/installed
 *   - GET  /marketplace/-/capabilities                  (75)
 *   - POST /marketplace/install                         (owner-only)
 *   - POST /marketplace/uninstall/{name}                (owner-only)
 *   - POST /marketplace/update/{name}?force=            (owner-only)
 *   - POST /marketplace/-/check-updates-now             (75, owner-only)
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
  // Phase 75 additions — safe defaults: empty string / empty array.
  category: string;
  readme_url: string;
  changelog_url: string;
  skill_dependencies: string[];
  permissions: string[];
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
  // Phase 75 additions — back-compat optional shapes for old installed.yaml rows.
  available_version?: string | null;
  update_checked_at?: string | null;
  category?: string;
  update_available?: boolean;
};

export type MarketplaceSkillsResponse = {
  ok: boolean;
  skills: MarketplaceSkillInfo[];
};

export type FeaturedSkillsResponse = MarketplaceSkillsResponse & {
  panel_enabled: boolean;
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

export type SkillDetails = {
  ok: boolean;
  skill: MarketplaceSkillInfo;
  documentation: {
    readme_url: string;
    changelog_url: string;
    manifest_url: string;
  };
  dependencies: string[];
  permissions: string[];
};

export type MarketplaceCategoriesResponse = {
  ok: boolean;
  categories: string[];
};

export type MarketplaceCheckUpdatesCounters = {
  scanned: number;
  up_to_date: number;
  updates_found: number;
  unreachable: number;
  skipped: number;
};

export type MarketplaceCheckUpdatesResponse = {
  ok: boolean;
  counters: MarketplaceCheckUpdatesCounters;
};

export type MarketplaceCapabilities = {
  ok: boolean;
  clawhub_enabled: boolean;
  panel_enabled: boolean;
  featured_panel_enabled: boolean;
  auto_update_skills: boolean;
  update_check_interval_seconds: number;
  sandbox_mode: boolean;
  skill_timeout_seconds: number;
  permissions_allowlist: string[];
  trusted_publishers: string[];
};

export async function searchSkills(
  query: string,
  limit = 20,
  category?: string,
): Promise<MarketplaceSkillInfo[]> {
  const q = (query || "").trim();
  if (!q) return [];
  const safe = Math.max(1, Math.min(Math.trunc(limit) || 20, 100));
  const cat = (category || "").trim().toLowerCase();
  const catParam = cat ? `&category=${encodeURIComponent(cat)}` : "";
  const data = await apiFetch<MarketplaceSkillsResponse>(
    `/marketplace/search?q=${encodeURIComponent(q)}&limit=${safe}${catParam}`,
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

export async function featuredSkills(limit = 12): Promise<FeaturedSkillsResponse> {
  const safe = Math.max(1, Math.min(Math.trunc(limit) || 12, 50));
  const data = await apiFetch<FeaturedSkillsResponse>(
    `/marketplace/featured?limit=${safe}`,
  );
  return {
    ok: Boolean(data?.ok),
    panel_enabled: Boolean(data?.panel_enabled),
    skills: Array.isArray(data?.skills) ? data.skills : [],
  };
}

export async function listMarketplaceCategories(): Promise<string[]> {
  const data = await apiFetch<MarketplaceCategoriesResponse>(
    `/marketplace/categories`,
  );
  return Array.isArray(data?.categories) ? data.categories : [];
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

export async function getSkillDetails(name: string): Promise<SkillDetails | null> {
  const nm = (name || "").trim();
  if (!nm) return null;
  try {
    return await apiFetch<SkillDetails>(
      `/marketplace/skill/${encodeURIComponent(nm)}/details`,
    );
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

export async function checkMarketplaceUpdatesNow(): Promise<MarketplaceCheckUpdatesResponse> {
  return apiFetch<MarketplaceCheckUpdatesResponse>(
    `/marketplace/-/check-updates-now`,
    { method: "POST" },
  );
}

export async function getMarketplaceCapabilities(): Promise<MarketplaceCapabilities | null> {
  try {
    return await apiFetch<MarketplaceCapabilities>(`/marketplace/-/capabilities`);
  } catch {
    return null;
  }
}
