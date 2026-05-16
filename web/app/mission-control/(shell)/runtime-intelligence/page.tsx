"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type IntelligencePayload = {
  runtime_awareness?: { operational_stability_matrix?: { stable?: boolean; pressure?: string } };
  intelligent_routing?: { advisory_first?: boolean; routing_metadata?: { provider_confidence?: number } };
  operational_recovery_state?: { degradation_signals?: unknown[] };
};

type PosturePayload = {
  operational_stability_matrix?: { stable?: boolean; pressure?: string };
};

type AdvisoriesPayload = {
  strategic_recommendations?: { title?: string; confidence_score?: number; risk_level?: string }[];
};

export default function RuntimeIntelligencePage() {
  const [intel, setIntel] = useState<IntelligencePayload>({});
  const [posture, setPosture] = useState<PosturePayload>({});
  const [advisories, setAdvisories] = useState<AdvisoriesPayload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [i, p, a] = await Promise.all([
        apiFetch<IntelligencePayload>("/mission-control/runtime/intelligence"),
        apiFetch<PosturePayload>("/mission-control/runtime/posture"),
        apiFetch<AdvisoriesPayload>("/mission-control/runtime/advisories"),
      ]);
      setIntel(i);
      setPosture(p);
      setAdvisories(a);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 15000);
    return () => clearInterval(t);
  }, [refresh]);

  const matrix = intel.runtime_awareness?.operational_stability_matrix ?? posture.operational_stability_matrix;
  const signalCount = intel.operational_recovery_state?.degradation_signals?.length ?? 0;
  const recs = advisories.strategic_recommendations ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Runtime intelligence</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Unified operational intelligence — routing, recovery, posture, and advisories
        </p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Stability</p>
          <p className="mt-1 text-lg font-medium">{matrix?.stable ? "Stable" : "Review"}</p>
          <p className="text-xs text-muted-foreground">Pressure: {matrix?.pressure ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Routing</p>
          <p className="mt-1 text-lg font-medium">{intel.intelligent_routing?.advisory_first ? "Advisory" : "—"}</p>
          <p className="text-xs text-muted-foreground">
            Confidence{" "}
            {intel.intelligent_routing?.routing_metadata?.provider_confidence != null
              ? intel.intelligent_routing.routing_metadata.provider_confidence.toFixed(2)
              : "—"}
          </p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Signals</p>
          <p className="mt-1 text-lg font-medium">{signalCount}</p>
          <p className="text-xs text-muted-foreground">Degradation indicators</p>
        </div>
      </section>
      {recs.length > 0 ? (
        <section className="space-y-2">
          <p className="text-xs uppercase text-muted-foreground">Advisories</p>
          {recs.slice(0, 4).map((r, i) => (
            <div key={i} className="rounded-lg border border-border/40 bg-card/20 px-4 py-3 text-sm">
              <p className="font-medium">{r.title}</p>
              <p className="text-xs text-muted-foreground">
                Risk {r.risk_level} · Confidence {r.confidence_score?.toFixed(2)}
              </p>
            </div>
          ))}
        </section>
      ) : null}
      <nav className="flex flex-wrap gap-3 text-sm">
        <Link href="/mission-control/runtime-overview" className="text-primary hover:underline">
          Runtime overview
        </Link>
        <Link href="/mission-control/governance" className="text-primary hover:underline">
          Governance
        </Link>
      </nav>
    </div>
  );
}
