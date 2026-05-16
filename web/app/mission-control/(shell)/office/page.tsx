"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchPanelResilient,
  operationalBanner,
  type OperationalStatus,
} from "@/lib/runtimeResilience";

type OfficeAgent = {
  agent_id: string;
  agent_type?: string;
  role?: string;
  persistent?: boolean;
  office_state?: string;
  system?: boolean;
  assignment?: { task_id?: string };
};

type OfficeEvent = {
  event_type?: string;
  severity?: string;
  count?: number;
};

type OfficePayload = {
  orchestrator?: { agent_id?: string; role?: string; health?: string; status?: string };
  agents?: OfficeAgent[];
  active_worker_count?: number;
  recent_events?: OfficeEvent[];
  critical_events?: OfficeEvent[];
  routing?: { provider?: string; model?: string; reason?: string; fallback_used?: boolean };
  privacy_mode?: string;
  pressure?: { queue?: boolean; retry?: boolean; deployment?: boolean };
  plugin_health?: { healthy?: number; failed?: number };
  active_tasks?: number;
  queued_tasks?: number;
  runtime_confidence?: {
    health?: string;
    uptime_hours?: number;
    restart_count?: number;
    active_recoveries?: number;
    provider_failures_24h?: number;
    plugin_failures_24h?: number;
  };
  confidence_summary?: string;
  office_operational_stream?: { office_interval_ms?: number; calmness_preserved?: boolean };
  hydration_progress?: { partial?: boolean; max_tier?: string };
};

const STATE_DOT: Record<string, string> = {
  active: "bg-emerald-500",
  busy: "bg-sky-500",
  idle: "bg-amber-400",
  recovering: "bg-violet-500",
  failed: "bg-red-500",
  offline: "bg-zinc-500",
};

const HEALTH_DOT: Record<string, string> = {
  healthy: "bg-emerald-500",
  warning: "bg-amber-400",
  degraded: "bg-amber-500",
  critical: "bg-red-500",
  recovering: "bg-violet-500",
};

const SEVERITY_CLASS: Record<string, string> = {
  info: "text-muted-foreground",
  warning: "text-amber-600 dark:text-amber-400",
  error: "text-orange-600 dark:text-orange-400",
  critical: "text-red-600 dark:text-red-400",
};

export default function OfficePage() {
  const [office, setOffice] = useState<OfficePayload>({});
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<OperationalStatus>("healthy");
  const [stale, setStale] = useState(false);

  const refresh = useCallback(async () => {
    const result = await fetchPanelResilient<OfficePayload>("/mission-control/office", {});
    setOffice(result.data);
    setStatus(result.status);
    setStale(Boolean(result.stale));
    setError(result.error ?? null);
  }, []);

  useEffect(() => {
    void refresh();
    const intervalMs = office.office_operational_stream?.office_interval_ms ?? 12000;
    const t = setInterval(() => void refresh(), intervalMs);
    return () => clearInterval(t);
  }, [refresh, office.office_operational_stream?.office_interval_ms]);

  const healthKey = office.orchestrator?.health ?? "healthy";
  const healthDot = HEALTH_DOT[healthKey] ?? HEALTH_DOT.healthy;
  const confidence = office.runtime_confidence;
  const workers = (office.agents ?? []).filter((a) => !a.system && a.office_state !== "offline");
  const events = office.recent_events ?? [];
  const routing = office.routing ?? {};

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border/60 pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">The Office</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Operational command center — health, readiness, orchestrator, active work, and routing
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className={`h-2 w-2 rounded-full ${healthDot}`} />
          <span className="capitalize text-muted-foreground">{healthKey}</span>
          {office.pressure?.queue || office.pressure?.retry ? (
            <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-400">
              pressure
            </span>
          ) : null}
          {(office.critical_events?.length ?? 0) > 0 ? (
            <span className="rounded bg-red-500/15 px-2 py-0.5 text-xs text-red-600 dark:text-red-400">
              {office.critical_events?.length} critical
            </span>
          ) : null}
        </div>
      </header>

      {confidence ? (
        <section className="rounded-lg border border-border/50 bg-card/40 px-4 py-3 text-sm">
          <p className="font-medium">Runtime confidence</p>
          <p className="mt-1 text-muted-foreground">
            {office.confidence_summary ?? `Status: ${confidence.health ?? "healthy"}`}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            Uptime {confidence.uptime_hours ?? 0}h · restarts {confidence.restart_count ?? 0} · provider issues 24h{" "}
            {confidence.provider_failures_24h ?? 0} · plugin issues 24h {confidence.plugin_failures_24h ?? 0}
          </p>
        </section>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-4 text-xs text-muted-foreground">
        <div className="rounded border border-border/40 px-3 py-2">
          <span className="block uppercase tracking-wider">Orchestrator</span>
          <span className="font-mono text-foreground">{office.orchestrator?.status ?? "active"}</span>
        </div>
        <div className="rounded border border-border/40 px-3 py-2">
          <span className="block uppercase tracking-wider">Workers</span>
          <span className="font-mono text-foreground">{office.active_worker_count ?? workers.length}</span>
        </div>
        <div className="rounded border border-border/40 px-3 py-2">
          <span className="block uppercase tracking-wider">Tasks</span>
          <span className="font-mono text-foreground">
            {office.active_tasks ?? 0} active · {office.queued_tasks ?? 0} queued
          </span>
        </div>
        <div className="rounded border border-border/40 px-3 py-2">
          <span className="block uppercase tracking-wider">Privacy</span>
          <span className="font-mono text-foreground">{office.privacy_mode ?? "observe"}</span>
        </div>
      </div>

      {routing.provider ? (
        <section className="rounded-lg border border-border/50 bg-card/40 px-4 py-3 text-sm">
          <span className="text-muted-foreground">Brain route </span>
          <span className="font-mono">
            {routing.provider}/{routing.model ?? "—"}
          </span>
          {routing.reason ? <span className="ml-2 text-muted-foreground">· {routing.reason}</span> : null}
        </section>
      ) : null}

      {operationalBanner(status, stale) ? (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-800 dark:text-amber-200">
          {operationalBanner(status, stale)}
        </p>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2 space-y-3">
          <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Runtime workers</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {workers.map((a) => (
              <article key={a.agent_id} className="rounded-lg border border-border/50 bg-card/30 p-3 text-sm">
                <div className="flex justify-between gap-2">
                  <span className="font-medium capitalize">{a.role ?? a.agent_type}</span>
                  <span
                    className={`h-2 w-2 rounded-full ${STATE_DOT[a.office_state ?? "offline"] ?? STATE_DOT.offline}`}
                  />
                </div>
                <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">{a.agent_id}</p>
              </article>
            ))}
          </div>
          {!workers.length && !error ? <p className="text-sm text-muted-foreground">No active workers.</p> : null}
        </section>

        <section className="rounded-lg border border-border/50 bg-card/30 p-4">
          <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Signal events</h2>
          <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto text-xs">
            {events.map((ev, i) => (
              <li key={`${ev.event_type}-${i}`} className="flex justify-between gap-2">
                <span className="font-mono">{ev.event_type}</span>
                <span className={SEVERITY_CLASS[ev.severity ?? "info"]}>
                  {ev.severity}
                  {(ev.count ?? 1) > 1 ? ` ×${ev.count}` : ""}
                </span>
              </li>
            ))}
            {!events.length ? <li className="text-muted-foreground">No signal events.</li> : null}
          </ul>
        </section>
      </div>
    </div>
  );
}
