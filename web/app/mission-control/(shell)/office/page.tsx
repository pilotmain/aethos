"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type OfficeAgent = {
  agent_id: string;
  agent_type?: string;
  office_state?: string;
  provider?: string;
  model?: string;
  assignment?: { task_id?: string };
  system?: boolean;
};

type RuntimeEvent = {
  event_type?: string;
  category?: string;
  severity?: string;
  count?: number;
};

type RuntimeHealth = {
  status?: string;
  severity?: string;
  color?: string;
  queue_pressure?: boolean;
  retry_pressure?: boolean;
  critical_events?: number;
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
};

const SEVERITY_CLASS: Record<string, string> = {
  info: "text-muted-foreground",
  warning: "text-amber-600 dark:text-amber-400",
  error: "text-orange-600 dark:text-orange-400",
  critical: "text-red-600 dark:text-red-400",
};

export default function OfficePage() {
  const [agents, setAgents] = useState<OfficeAgent[]>([]);
  const [events, setEvents] = useState<RuntimeEvent[]>([]);
  const [health, setHealth] = useState<RuntimeHealth>({});
  const [routing, setRouting] = useState<{ provider?: string; model?: string; reason?: string; fallback_used?: boolean }>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const runtime = await apiFetch<{
        office?: { agents?: OfficeAgent[]; recent_events?: RuntimeEvent[] };
        runtime_health?: RuntimeHealth;
        routing_summary?: { provider?: string; model?: string; reason?: string; fallback_used?: boolean };
      }>("/mission-control/runtime");
      setAgents(runtime.office?.agents ?? []);
      setEvents(runtime.office?.recent_events ?? []);
      setHealth(runtime.runtime_health ?? {});
      setRouting(runtime.routing_summary ?? {});
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load runtime");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 10000);
    return () => clearInterval(t);
  }, [refresh]);

  const healthKey = health.status ?? "healthy";
  const healthDot = HEALTH_DOT[healthKey] ?? HEALTH_DOT.healthy;
  const activeAgents = agents.filter((a) => a.office_state !== "offline" && !a.system);

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border/60 pb-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">The Office</h1>
          <p className="mt-1 text-sm text-muted-foreground">Runtime health, active agents, and prioritized events</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className={`h-2 w-2 rounded-full ${healthDot}`} />
          <span className="capitalize text-muted-foreground">{healthKey}</span>
          {(health.queue_pressure || health.retry_pressure) && (
            <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-400">
              pressure
            </span>
          )}
          {(health.critical_events ?? 0) > 0 && (
            <span className="rounded bg-red-500/15 px-2 py-0.5 text-xs text-red-600 dark:text-red-400">
              {health.critical_events} critical
            </span>
          )}
        </div>
      </header>

      {routing.provider ? (
        <section className="rounded-lg border border-border/60 bg-card/50 px-4 py-3 text-sm">
          <span className="text-muted-foreground">Provider route </span>
          <span className="font-mono">
            {routing.provider}/{routing.model ?? "—"}
          </span>
          {routing.reason ? <span className="ml-2 text-muted-foreground">· {routing.reason}</span> : null}
          {routing.fallback_used ? (
            <span className="ml-2 rounded bg-amber-500/15 px-1.5 py-0.5 text-xs text-amber-600 dark:text-amber-400">
              fallback
            </span>
          ) : null}
        </section>
      ) : null}

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <div className="grid gap-8 lg:grid-cols-3">
        <section className="lg:col-span-2 space-y-4">
          <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Active agents ({activeAgents.length})
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {activeAgents.map((a) => {
              const st = a.office_state ?? "offline";
              return (
                <article
                  key={a.agent_id}
                  className="rounded-lg border border-border/50 bg-card/40 p-4 transition-colors hover:bg-card/70"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium capitalize">{a.agent_type ?? "agent"}</p>
                      <p className="truncate font-mono text-[11px] text-muted-foreground">{a.agent_id}</p>
                    </div>
                    <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${STATE_DOT[st] ?? STATE_DOT.offline}`} />
                  </div>
                  {a.assignment?.task_id ? (
                    <p className="mt-2 truncate font-mono text-[11px] text-muted-foreground">{a.assignment.task_id}</p>
                  ) : null}
                </article>
              );
            })}
          </div>
          {!activeAgents.length && !error ? (
            <p className="text-sm text-muted-foreground">No active runtime agents.</p>
          ) : null}
        </section>

        <section className="rounded-lg border border-border/50 bg-card/40 p-4">
          <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Events</h2>
          <ul className="mt-4 max-h-96 space-y-3 overflow-y-auto text-xs">
            {events.map((ev, i) => {
              const sev = ev.severity ?? "info";
              return (
                <li key={`${ev.event_type}-${i}`} className="flex justify-between gap-2 border-b border-border/30 pb-2">
                  <span className="font-mono text-foreground">{ev.event_type}</span>
                  <span className={`shrink-0 ${SEVERITY_CLASS[sev] ?? SEVERITY_CLASS.info}`}>
                    {sev}
                    {(ev.count ?? 1) > 1 ? ` ×${ev.count}` : ""}
                  </span>
                </li>
              );
            })}
            {!events.length ? <li className="text-muted-foreground">No recent events.</li> : null}
          </ul>
        </section>
      </div>
    </div>
  );
}
