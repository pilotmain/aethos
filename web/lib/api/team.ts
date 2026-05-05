/** Derive team counts from Mission Control state (`orchestration` slice). */

export type TeamMetrics = { total: number; active: number };

export function teamMetricsFromState(state: Record<string, unknown> | null): TeamMetrics {
  if (!state) return { total: 0, active: 0 };
  const orch = state.orchestration as { roles?: unknown[]; assignments?: unknown[] } | undefined;
  const roles = Array.isArray(orch?.roles) ? orch.roles : [];
  const assigns = Array.isArray(orch?.assignments) ? orch.assignments : [];
  const active = assigns.filter((a) => {
    const st = String((a as { status?: string }).status || "").toLowerCase();
    return st && st !== "cancelled";
  }).length;
  const roleHandles = new Set(
    roles.map((r) => String((r as { agent_handle?: string }).agent_handle || "").trim()).filter(Boolean),
  );
  const total = Math.max(roleHandles.size, roles.length);
  return { total, active: active || assigns.length };
}
