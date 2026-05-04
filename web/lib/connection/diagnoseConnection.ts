import { DEFAULT_API_BASE } from "@/lib/config";

import type { ConnectionDiagnosis } from "./types";

async function probeHealth(base: string): Promise<{
  ok: boolean;
  corsOk: boolean;
  status?: number;
  error?: string;
}> {
  const url = `${base.replace(/\/$/, "")}/api/v1/health`;
  try {
    const r = await fetch(url, { method: "GET", mode: "cors", cache: "no-store" });
    return { ok: r.ok, corsOk: true, status: r.status };
  } catch (e) {
    if (e instanceof TypeError) {
      return { ok: false, corsOk: false, error: e.message };
    }
    return { ok: false, corsOk: false, error: String(e) };
  }
}

function collectAlternateBases(configured: string): string[] {
  const norm = (s: string) => s.trim().replace(/\/$/, "");
  const set = new Set<string>();
  for (const b of [
    DEFAULT_API_BASE,
    norm(configured),
    "http://127.0.0.1:8010",
    "http://127.0.0.1:8120",
    "http://localhost:8010",
    "http://localhost:8120",
  ]) {
    if (b) set.add(norm(b));
  }
  return Array.from(set);
}

/**
 * Probe `/api/v1/health` on the configured API base and common local alternates.
 * Used to distinguish "wrong saved URL" from "API down" and to power recovery UI.
 */
export async function diagnoseConnection(apiBase: string): Promise<ConnectionDiagnosis> {
  const base = apiBase.trim().replace(/\/$/, "") || DEFAULT_API_BASE;
  const primary = await probeHealth(base);

  let suggestedApiBase: string | undefined;
  let alternateReachable = false;

  if (!primary.ok) {
    for (const alt of collectAlternateBases(base)) {
      if (alt === base) continue;
      const p = await probeHealth(alt);
      if (p.ok) {
        alternateReachable = true;
        suggestedApiBase = alt;
        break;
      }
    }
  }

  return {
    apiBase: base,
    healthReachable: primary.ok,
    corsOk: primary.corsOk,
    alternateReachable,
    suggestedApiBase,
    error: primary.error,
  };
}
