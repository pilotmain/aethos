import { apiFetch } from "@/lib/api/client";

export type HealthPayload = {
  status: string;
  app?: string;
  env?: string;
};

/** GET /api/v1/health — no sensitive data; uses same origin + optional auth headers as other calls. */
export async function fetchHealth(): Promise<{ ok: boolean; payload?: HealthPayload }> {
  try {
    const payload = await apiFetch<HealthPayload>("/health");
    const ok = (payload.status || "").toLowerCase() === "ok";
    return { ok, payload };
  } catch {
    return { ok: false };
  }
}
