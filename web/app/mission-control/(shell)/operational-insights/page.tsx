"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type IntelPayload = {
  signals?: Array<{ kind?: string; severity?: string; value?: unknown }>;
  suggestions?: Array<{ kind?: string; message?: string }>;
  summaries?: Record<string, string>;
  enterprise_operational_state?: { health?: string; active_risk_count?: number };
};

type RecPayload = {
  recommendations?: Array<{
    kind?: string;
    message?: string;
    confidence?: number;
    reason?: string;
    suggested_next_step?: string;
  }>;
};

type HealthPayload = {
  overall?: string;
  categories?: Record<string, string>;
};

type PackRow = {
  pack_id?: string;
  name?: string;
  pack_type?: string;
  enabled?: boolean;
  health?: string;
  trust_tier?: string;
  operational_metrics?: { runs_24h?: number; success_rate?: number };
};

export default function OperationalInsightsPage() {
  const [intel, setIntel] = useState<IntelPayload>({});
  const [recs, setRecs] = useState<RecPayload>({});
  const [packs, setPacks] = useState<PackRow[]>([]);
  const [health, setHealth] = useState<HealthPayload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [i, r, p, h, trust] = await Promise.all([
        apiFetch<IntelPayload>("/mission-control/operational-intelligence"),
        apiFetch<RecPayload>("/mission-control/runtime-recommendations"),
        apiFetch<{ packs?: PackRow[] }>("/mission-control/automation-packs"),
        apiFetch<HealthPayload>("/mission-control/runtime/health"),
        apiFetch<{ operational_trust_score?: number }>("/mission-control/governance/trust"),
      ]);
      setIntel({ ...i, summaries: { ...(i.summaries ?? {}), trust_score: String(trust.operational_trust_score ?? "—") } });
      setRecs(r);
      setPacks(p.packs ?? []);
      setHealth(h);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const runPack = async (packId: string) => {
    await apiFetch(`/mission-control/automation-packs/${encodeURIComponent(packId)}/run`, {
      method: "POST",
    });
    void refresh();
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Operational insights</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Enterprise intelligence — advisory recommendations, governed automation
        </p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2 text-sm">
        <div className="rounded border border-border/50 p-4">
          <p className="text-xs uppercase text-muted-foreground">Enterprise health</p>
          <p className="mt-1 font-medium">{health.overall ?? intel.enterprise_operational_state?.health ?? "—"}</p>
        </div>
        <div className="rounded border border-border/50 p-4">
          <p className="text-xs uppercase text-muted-foreground">Active risks</p>
          <p className="mt-1">{intel.enterprise_operational_state?.active_risk_count ?? 0}</p>
        </div>
      </div>
      {(intel.suggestions ?? []).length > 0 ? (
        <section className="rounded border border-border/50 p-4 text-sm">
          <h2 className="font-medium">Suggestions</h2>
          <ul className="mt-2 space-y-2 text-muted-foreground">
            {(intel.suggestions ?? []).map((s, i) => (
              <li key={i}>{s.message}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {(recs.recommendations ?? []).length > 0 ? (
        <section className="rounded border border-border/50 p-4 text-sm">
          <h2 className="font-medium">Recommendations</h2>
          <ul className="mt-2 space-y-2">
            {(recs.recommendations ?? []).map((r, i) => (
              <li key={i} className="text-muted-foreground">
                {r.message}{" "}
                <span className="text-xs">({Math.round((r.confidence ?? 0) * 100)}% confidence)</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <section className="rounded border border-border/50 p-4 text-sm">
        <h2 className="font-medium">Automation packs</h2>
        <ul className="mt-2 space-y-3">
          {packs.length === 0 ? (
            <li className="text-muted-foreground">No automation packs installed.</li>
          ) : (
            packs.map((p) => (
              <li key={p.pack_id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {p.name ?? p.pack_id} · {p.pack_type} · {p.health}
                </span>
                <button
                  type="button"
                  className="text-xs underline disabled:opacity-50"
                  disabled={!p.enabled}
                  onClick={() => p.pack_id && void runPack(p.pack_id)}
                >
                  Run (operator)
                </button>
              </li>
            ))
          )}
        </ul>
      </section>
    </div>
  );
}
