"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import {
  fetchPanelResilient,
  operationalBanner,
  type OperationalStatus,
} from "@/lib/runtimeResilience";

type PanelState<T> = {
  data: T;
  status: OperationalStatus;
  error?: string;
  stale?: boolean;
};

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

type RecoveryPayload = {
  operational_status?: string;
  recovery_recommendations?: { title?: string; detail?: string }[];
  truth_integrity_score?: number;
};

const emptyIntel: IntelligencePayload = {};
const emptyPosture: PosturePayload = {};
const emptyAdvisories: AdvisoriesPayload = {};
const emptyRecovery: RecoveryPayload = {};

export default function RuntimeIntelligencePage() {
  const [intel, setIntel] = useState<PanelState<IntelligencePayload>>({ data: emptyIntel, status: "healthy" });
  const [posture, setPosture] = useState<PanelState<PosturePayload>>({ data: emptyPosture, status: "healthy" });
  const [advisories, setAdvisories] = useState<PanelState<AdvisoriesPayload>>({
    data: emptyAdvisories,
    status: "healthy",
  });
  const [recovery, setRecovery] = useState<PanelState<RecoveryPayload>>({ data: emptyRecovery, status: "healthy" });

  const refresh = useCallback(async () => {
    const [i, p, a, r] = await Promise.all([
      fetchPanelResilient<IntelligencePayload>("/mission-control/runtime/intelligence", emptyIntel),
      fetchPanelResilient<PosturePayload>("/mission-control/runtime/posture", emptyPosture),
      fetchPanelResilient<AdvisoriesPayload>("/mission-control/runtime/advisories", emptyAdvisories),
      fetchPanelResilient<RecoveryPayload>("/mission-control/runtime-recovery", emptyRecovery),
    ]);
    setIntel(i);
    setPosture(p);
    setAdvisories(a);
    setRecovery(r);
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 15000);
    return () => clearInterval(t);
  }, [refresh]);

  const worst: OperationalStatus = [intel, posture, advisories, recovery].some((p) => p.status === "offline")
    ? "offline"
    : [intel, posture, advisories, recovery].some((p) => p.status === "degraded" || p.status === "partial")
      ? "degraded"
      : [intel, posture, advisories, recovery].some((p) => p.stale)
        ? "stale"
        : "healthy";

  const matrix =
    intel.data.runtime_awareness?.operational_stability_matrix ?? posture.data.operational_stability_matrix;
  const signalCount = intel.data.operational_recovery_state?.degradation_signals?.length ?? 0;
  const recs = advisories.data.strategic_recommendations ?? [];
  const panelErrors = [intel, posture, advisories, recovery].filter((p) => p.error).map((p) => p.error);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Runtime intelligence</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Independent panels — routing, posture, advisories, and recovery
        </p>
      </header>
      {operationalBanner(worst) ? (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-800 dark:text-amber-200">
          {operationalBanner(worst)}
        </p>
      ) : null}
      {panelErrors.length > 0 ? (
        <p className="text-sm text-destructive">{panelErrors[0]}</p>
      ) : null}
      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Stability</p>
          <p className="mt-1 text-lg font-medium">{matrix?.stable ? "Stable" : "Review"}</p>
          <p className="text-xs text-muted-foreground">Pressure: {matrix?.pressure ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Routing</p>
          <p className="mt-1 text-lg font-medium">
            {intel.data.intelligent_routing?.advisory_first ? "Advisory" : "—"}
          </p>
          <p className="text-xs text-muted-foreground">
            Confidence{" "}
            {intel.data.intelligent_routing?.routing_metadata?.provider_confidence != null
              ? intel.data.intelligent_routing.routing_metadata.provider_confidence.toFixed(2)
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
      {recovery.data.recovery_recommendations && recovery.data.recovery_recommendations.length > 0 ? (
        <section className="space-y-2">
          <p className="text-xs uppercase text-muted-foreground">Recovery</p>
          {recovery.data.recovery_recommendations.slice(0, 3).map((r, i) => (
            <div key={i} className="rounded-lg border border-border/40 bg-card/20 px-4 py-3 text-sm">
              <p className="font-medium">{r.title}</p>
              <p className="text-xs text-muted-foreground">{r.detail}</p>
            </div>
          ))}
        </section>
      ) : null}
      <nav className="flex flex-wrap gap-3 text-sm">
        <Link href="/mission-control/runtime-overview" className="text-primary hover:underline">
          Runtime overview
        </Link>
        <Link href="/mission-control/runtime-recovery" className="text-primary hover:underline">
          Runtime recovery
        </Link>
        <Link href="/mission-control/governance" className="text-primary hover:underline">
          Governance
        </Link>
      </nav>
    </div>
  );
}
