"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type OfficeAgent = {
  agent_id: string;
  agent_type?: string;
  office_state?: string;
  lifecycle?: string;
  provider?: string;
  model?: string;
  assignment?: { task_id?: string; workflow_id?: string };
  system?: boolean;
};

type RuntimeEvent = {
  event_type?: string;
  category?: string;
  severity?: string;
  timestamp?: string;
};

const STATE_COLOR: Record<string, string> = {
  active: "bg-emerald-500",
  busy: "bg-sky-500",
  idle: "bg-amber-400",
  recovering: "bg-violet-500",
  failed: "bg-red-500",
  offline: "bg-zinc-400",
  spawned: "bg-emerald-400",
  suspended: "bg-zinc-500",
};

export default function OfficePage() {
  const [agents, setAgents] = useState<OfficeAgent[]>([]);
  const [events, setEvents] = useState<RuntimeEvent[]>([]);
  const [health, setHealth] = useState<{ color?: string; status?: string }>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const runtime = await apiFetch<{
        office?: { agents?: OfficeAgent[]; recent_events?: RuntimeEvent[] };
        runtime_health?: { color?: string; status?: string };
      }>("/mission-control/runtime");
      setAgents(runtime.office?.agents ?? []);
      setEvents(runtime.office?.recent_events ?? []);
      setHealth(runtime.runtime_health ?? {});
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load runtime");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 8000);
    return () => clearInterval(t);
  }, [refresh]);

  const healthColor =
    health.color === "red" ? "bg-red-500" : health.color === "amber" ? "bg-amber-400" : "bg-emerald-500";

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">The Office</h1>
          <p className="text-sm text-muted-foreground">Runtime topology — agents, tasks, and live events</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className={`h-2.5 w-2.5 rounded-full ${healthColor}`} />
          Runtime {health.status ?? "unknown"}
        </div>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {agents.map((a) => {
              const st = a.office_state ?? "offline";
              const dot = STATE_COLOR[st] ?? STATE_COLOR.offline;
              return (
                <div key={a.agent_id} className="rounded-lg border bg-card p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{a.agent_type ?? "agent"}</p>
                      <p className="truncate text-xs text-muted-foreground">{a.agent_id}</p>
                    </div>
                    <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} title={st} />
                  </div>
                  <p className="mt-3 text-xs capitalize text-muted-foreground">{st}</p>
                  {a.assignment?.task_id ? (
                    <p className="mt-1 truncate font-mono text-xs text-muted-foreground">→ {a.assignment.task_id}</p>
                  ) : null}
                  {(a.provider || a.model) && (
                    <p className="mt-1 font-mono text-xs">{[a.provider, a.model].filter(Boolean).join(" / ")}</p>
                  )}
                </div>
              );
            })}
          </div>
          {!agents.length && !error ? (
            <p className="text-sm text-muted-foreground">No runtime agents yet.</p>
          ) : null}
        </div>
        <div className="rounded-lg border bg-card p-4">
          <h2 className="text-sm font-medium">Recent runtime events</h2>
          <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto text-xs">
            {events.map((ev, i) => (
              <li key={`${ev.event_type}-${i}`} className="border-b border-border/50 pb-2">
                <span className="font-mono">{ev.event_type}</span>
                <span className="ml-2 text-muted-foreground">{ev.category}</span>
                <span className="ml-1 text-muted-foreground">({ev.severity})</span>
              </li>
            ))}
            {!events.length ? <li className="text-muted-foreground">No events yet.</li> : null}
          </ul>
        </div>
      </div>
    </div>
  );
}
