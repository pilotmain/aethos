"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type Differentiators = {
  advantages?: string[];
  privacy_posture?: { privacy_posture?: Record<string, unknown>; blocked_operations?: number };
  brain_routing?: { brain_routing?: Record<string, unknown> };
  operational_intelligence?: { insights?: Array<{ kind?: string; message?: string; severity?: string }> };
  marketplace_health?: { installed_count?: number; available_count?: number };
};

export default function DifferentiatorsPage() {
  const [data, setData] = useState<Differentiators>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const d = await apiFetch<Differentiators>("/mission-control/differentiators");
      setData(d);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const posture = data.privacy_posture?.privacy_posture ?? {};
  const brain = data.brain_routing?.brain_routing ?? {};
  const insights = data.operational_intelligence?.insights ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      <header className="border-b border-border/60 pb-6">
        <h1 className="text-xl font-semibold tracking-tight">AethOS advantages</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Runtime-backed differentiators — parity-tested where it matters, better where it counts.
        </p>
      </header>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <section className="rounded-lg border border-border/50 bg-card/40 p-4">
        <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Capabilities</h2>
        <ul className="mt-3 flex flex-wrap gap-2">
          {(data.advantages ?? []).map((a) => (
            <li key={a} className="rounded bg-muted/50 px-2 py-1 font-mono text-[11px]">
              {a.replace(/_/g, " ")}
            </li>
          ))}
        </ul>
      </section>

      <div className="grid gap-4 sm:grid-cols-2">
        <article className="rounded-lg border border-border/50 p-4">
          <h2 className="text-xs font-medium uppercase text-muted-foreground">Privacy posture</h2>
          <p className="mt-2 text-sm">
            Mode <span className="font-mono">{String(posture.mode ?? "—")}</span>
            {posture.local_first ? " · local-first" : ""}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Blocked ops: {data.privacy_posture?.blocked_operations ?? 0}
          </p>
        </article>
        <article className="rounded-lg border border-border/50 p-4">
          <h2 className="text-xs font-medium uppercase text-muted-foreground">Brain routing</h2>
          <p className="mt-2 font-mono text-sm">
            {String(brain.selected_provider ?? "—")}/{String(brain.selected_model ?? "—")}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{String(brain.reason ?? "")}</p>
        </article>
      </div>

      <section className="rounded-lg border border-border/50 p-4">
        <h2 className="text-xs font-medium uppercase text-muted-foreground">Operational insights</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {insights.map((i) => (
            <li key={i.kind} className="flex justify-between gap-2">
              <span>{i.message}</span>
              <span className="text-xs text-muted-foreground">{i.severity}</span>
            </li>
          ))}
          {!insights.length ? <li className="text-muted-foreground">No active insights.</li> : null}
        </ul>
      </section>

      {data.marketplace_health ? (
        <p className="text-xs text-muted-foreground">
          Marketplace: {data.marketplace_health.installed_count ?? 0} installed /{" "}
          {data.marketplace_health.available_count ?? 0} available
        </p>
      ) : null}
    </div>
  );
}
