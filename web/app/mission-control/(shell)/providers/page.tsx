"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type ProvidersPayload = {
  provider_inventory?: Record<string, unknown>;
  recent_provider_actions?: Array<{ provider?: string; action?: string; status?: string }>;
  routing_summary?: { provider?: string; model?: string; reason?: string };
};

export default function ProvidersPage() {
  const [data, setData] = useState<ProvidersPayload>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const p = await apiFetch<ProvidersPayload>("/mission-control/providers");
      setData(p);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load providers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const inventory = data.provider_inventory ?? {};
  const actions = data.recent_provider_actions ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Providers</h1>
        <p className="mt-1 text-sm text-muted-foreground">What AethOS is using to execute work — live from runtime</p>
      </header>

      {loading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {data.routing_summary?.provider ? (
        <section className="rounded-lg border border-border/50 bg-card/40 px-4 py-3 text-sm">
          Active route:{" "}
          <span className="font-mono">
            {data.routing_summary.provider}/{data.routing_summary.model ?? "—"}
          </span>
          {data.routing_summary.reason ? <span className="text-muted-foreground"> · {data.routing_summary.reason}</span> : null}
        </section>
      ) : null}

      <section className="space-y-2">
        <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Inventory</h2>
        {!Object.keys(inventory).length && !loading ? (
          <p className="text-sm text-muted-foreground">No provider inventory loaded.</p>
        ) : (
          <ul className="space-y-2">
            {Object.entries(inventory).map(([id, row]) => (
              <li key={id} className="rounded border border-border/40 px-3 py-2 text-sm font-mono">
                {id}
                {typeof row === "object" && row !== null ? (
                  <span className="ml-2 text-muted-foreground text-xs">{JSON.stringify(row).slice(0, 80)}</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Recent actions</h2>
        <ul className="space-y-1 text-sm">
          {actions.map((a, i) => (
            <li key={i} className="text-muted-foreground">
              {a.provider} — {a.action}
              {a.status ? ` (${a.status})` : ""}
            </li>
          ))}
          {!actions.length && !loading ? <li>No recent provider actions.</li> : null}
        </ul>
      </section>
    </div>
  );
}
