"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type ReadinessPayload = {
  runtime_readiness_score?: number;
  enterprise_readiness?: { enterprise_ready?: boolean; production_grade?: boolean };
};

type OverviewPayload = {
  headline?: string;
  trust_score?: number;
  calm_score?: number;
  runtime_readiness_score?: number;
  identity?: { orchestrator_label?: string; health_label?: string; trust_label?: string };
  pressure?: { level?: string; queue_pressure?: boolean };
  narrative_preview?: string;
  health?: { overall?: string; categories?: Record<string, string> };
};

type CalmPayload = {
  runtime_calmness?: { calm_score?: number; feels_calm?: boolean; pressure_level?: string };
  operational_quality?: { quality_score?: number };
};

export default function RuntimeOverviewPage() {
  const [overview, setOverview] = useState<OverviewPayload>({});
  const [calm, setCalm] = useState<CalmPayload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [o, c, r] = await Promise.all([
        apiFetch<OverviewPayload>("/mission-control/runtime/overview"),
        apiFetch<CalmPayload>("/mission-control/runtime/calmness"),
        apiFetch<ReadinessPayload>("/mission-control/runtime/readiness"),
      ]);
      setOverview({ ...o, runtime_readiness_score: r.runtime_readiness_score ?? o.runtime_readiness_score });
      setCalm(c);
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

  const calmScore = calm.runtime_calmness?.calm_score ?? overview.calm_score;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Runtime overview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Unified enterprise operator view — trust, calmness, and operational identity
        </p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {overview.runtime_readiness_score != null ? (
        <p className="text-sm text-muted-foreground">
          Enterprise readiness score: <span className="font-medium text-foreground">{overview.runtime_readiness_score.toFixed(2)}</span>
        </p>
      ) : null}
      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Trust</p>
          <p className="mt-1 text-lg font-medium">
            {overview.trust_score != null ? overview.trust_score.toFixed(2) : "—"}
          </p>
          <p className="text-xs text-muted-foreground">{overview.identity?.trust_label}</p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Calmness</p>
          <p className="mt-1 text-lg font-medium">{calmScore != null ? calmScore.toFixed(2) : "—"}</p>
          <p className="text-xs text-muted-foreground">
            {calm.runtime_calmness?.feels_calm ? "Operational calm" : "Elevated activity"}
          </p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Health</p>
          <p className="mt-1 text-lg font-medium capitalize">
            {overview.health?.overall ?? overview.identity?.health_label ?? "—"}
          </p>
          <p className="text-xs text-muted-foreground">Pressure: {overview.pressure?.level ?? "low"}</p>
        </div>
      </section>
      {overview.headline ? (
        <p className="rounded-lg border border-border/40 bg-card/30 px-4 py-3 text-sm">{overview.headline}</p>
      ) : null}
      {overview.narrative_preview ? (
        <p className="text-sm text-muted-foreground">{overview.narrative_preview}</p>
      ) : null}
      <nav className="flex flex-wrap gap-3 text-sm">
        <Link href="/mission-control/office" className="text-primary hover:underline">
          Office
        </Link>
        <Link href="/mission-control/governance" className="text-primary hover:underline">
          Governance
        </Link>
        <Link href="/mission-control/operational-insights" className="text-primary hover:underline">
          Insights
        </Link>
      </nav>
    </div>
  );
}
