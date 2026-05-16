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

type EnterprisePayload = {
  maturity?: string;
  positioning?: string;
  strategic_alerts?: number;
  adaptive_signals?: number;
  coordination_signals?: number;
  efficiency_signals?: number;
  strategic_insights?: number;
  outlook?: string;
  worker_ecosystem?: string;
  ecosystem_health?: string;
  optimization_quality?: number;
};

type EcosystemPayload = {
  ecosystem_operational_health?: { status?: string; composite_health?: number };
};

type OutlookPayload = {
  enterprise_operational_outlook?: { outlook?: string; summary?: string };
};

type StrategyPayload = {
  operational_trajectory_summary?: { direction?: string; summary?: string };
  runtime_maturity_summary?: { maturity_level?: string };
};

export default function RuntimeOverviewPage() {
  const [overview, setOverview] = useState<OverviewPayload>({});
  const [calm, setCalm] = useState<CalmPayload>({});
  const [enterprise, setEnterprise] = useState<EnterprisePayload>({});
  const [strategy, setStrategy] = useState<StrategyPayload>({});
  const [outlook, setOutlook] = useState<OutlookPayload>({});
  const [ecosystem, setEcosystem] = useState<EcosystemPayload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [o, c, r, ent, strat, ol, eco] = await Promise.all([
        apiFetch<OverviewPayload>("/mission-control/runtime/overview"),
        apiFetch<CalmPayload>("/mission-control/runtime/calmness"),
        apiFetch<ReadinessPayload>("/mission-control/runtime/readiness"),
        apiFetch<EnterprisePayload>("/mission-control/enterprise/overview"),
        apiFetch<StrategyPayload>("/mission-control/runtime/strategy"),
        apiFetch<OutlookPayload>("/mission-control/runtime/outlook"),
        apiFetch<EcosystemPayload>("/mission-control/ecosystem/health"),
      ]);
      setOverview({ ...o, runtime_readiness_score: r.runtime_readiness_score ?? o.runtime_readiness_score });
      setCalm(c);
      setEnterprise(ent);
      setStrategy(strat);
      setOutlook(ol);
      setEcosystem(eco);
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
      {(enterprise.maturity || strategy.operational_trajectory_summary?.summary) ? (
        <section className="rounded-lg border border-border/40 bg-card/20 px-4 py-3 text-sm space-y-1">
          <p className="text-xs uppercase text-muted-foreground">Strategic posture</p>
          {enterprise.maturity ? (
            <p>
              Maturity: <span className="font-medium capitalize">{enterprise.maturity}</span>
              {enterprise.positioning ? (
                <span className="text-muted-foreground"> — {enterprise.positioning}</span>
              ) : null}
            </p>
          ) : null}
          {strategy.operational_trajectory_summary?.summary ? (
            <p className="text-muted-foreground">{strategy.operational_trajectory_summary.summary}</p>
          ) : null}
          {(enterprise.strategic_alerts != null || enterprise.adaptive_signals != null) ? (
            <p className="text-xs text-muted-foreground">
              Alerts {enterprise.strategic_alerts ?? 0} · Signals {enterprise.adaptive_signals ?? 0}
              {enterprise.coordination_signals != null ? ` · Coordination ${enterprise.coordination_signals}` : ""}
            </p>
          ) : null}
          {enterprise.worker_ecosystem ? (
            <p className="text-xs text-muted-foreground">Worker ecosystem: {enterprise.worker_ecosystem}</p>
          ) : null}
          {enterprise.ecosystem_health || ecosystem.ecosystem_operational_health?.status ? (
            <p className="text-xs text-muted-foreground">
              Ecosystem: {enterprise.ecosystem_health ?? ecosystem.ecosystem_operational_health?.status}
              {enterprise.optimization_quality != null
                ? ` · Optimization ${enterprise.optimization_quality.toFixed(2)}`
                : null}
            </p>
          ) : null}
          {outlook.enterprise_operational_outlook?.summary ? (
            <p className="text-xs text-muted-foreground">{outlook.enterprise_operational_outlook.summary}</p>
          ) : null}
        </section>
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
        <Link href="/mission-control/runtime-intelligence" className="text-primary hover:underline">
          Runtime intelligence
        </Link>
      </nav>
    </div>
  );
}
