"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { fetchPanelResilient, operationalBanner, type OperationalStatus } from "@/lib/runtimeResilience";

type RecoveryPayload = {
  operational_status?: string;
  failed_slices?: string[];
  hydration_retries?: number;
  stale_caches?: boolean;
  degraded_panels?: string[];
  recovery_recommendations?: { title?: string; detail?: string }[];
  truth_integrity_score?: number;
  hydration_duration_ms?: number;
  hydration_queue?: { tiers?: string[] };
  pending_slices?: Record<string, number>;
  throttling_state?: { active?: boolean; pressure_level?: string };
  cache_utilization?: { hit_rate?: number };
  slice_persistence_health?: { healthy?: boolean; persisted_count?: number };
};

export default function RuntimeRecoveryPage() {
  const [recovery, setRecovery] = useState<RecoveryPayload>({});
  const [status, setStatus] = useState<OperationalStatus>("healthy");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const r = await fetchPanelResilient<RecoveryPayload>("/mission-control/runtime-recovery", {});
    setRecovery(r.data);
    setStatus((r.data.operational_status as OperationalStatus) || r.status);
    setError(r.error ?? null);
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 12000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Runtime recovery</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Hydration health, stale caches, and recovery recommendations
        </p>
      </header>
      {operationalBanner(status) ? (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-800 dark:text-amber-200">
          {operationalBanner(status)}
        </p>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <section className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Status</p>
          <p className="mt-1 text-lg font-medium capitalize">{recovery.operational_status ?? status}</p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Integrity</p>
          <p className="mt-1 text-lg font-medium">
            {recovery.truth_integrity_score != null ? recovery.truth_integrity_score.toFixed(2) : "—"}
          </p>
        </div>
      </section>
      {recovery.cache_utilization?.hit_rate != null ? (
        <p className="text-sm text-muted-foreground">
          Cache hit rate: {(recovery.cache_utilization.hit_rate * 100).toFixed(0)}%
          {recovery.slice_persistence_health?.persisted_count != null
            ? ` · Persisted slices: ${recovery.slice_persistence_health.persisted_count}`
            : ""}
        </p>
      ) : null}
      {recovery.throttling_state?.active ? (
        <p className="text-sm text-amber-700 dark:text-amber-300">
          Operational throttling active (pressure: {recovery.throttling_state.pressure_level ?? "high"})
        </p>
      ) : null}
      {(recovery.failed_slices?.length ?? 0) > 0 ? (
        <p className="text-sm text-muted-foreground">Slow slices: {recovery.failed_slices?.join(", ")}</p>
      ) : null}
      {(recovery.recovery_recommendations ?? []).map((r, i) => (
        <div key={i} className="rounded-lg border border-border/40 bg-card/20 px-4 py-3 text-sm">
          <p className="font-medium">{r.title}</p>
          <p className="text-xs text-muted-foreground">{r.detail}</p>
        </div>
      ))}
      <nav className="flex flex-wrap gap-3 text-sm">
        <Link href="/mission-control/runtime-intelligence" className="text-primary hover:underline">
          Runtime intelligence
        </Link>
        <Link href="/mission-control/office" className="text-primary hover:underline">
          Office
        </Link>
      </nav>
    </div>
  );
}
