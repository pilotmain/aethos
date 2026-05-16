"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type PluginRow = {
  plugin_id: string;
  name?: string;
  version?: string;
  trust_tier?: string;
  installed?: boolean;
  runtime_state?: string;
  verified?: boolean;
  permissions?: string[];
};

type Summary = {
  installed_count?: number;
  available_count?: number;
  plugin_health?: { healthy_count?: number; failed_count?: number; warnings?: unknown[] };
};

export default function PluginsPage() {
  const [installed, setInstalled] = useState<PluginRow[]>([]);
  const [available, setAvailable] = useState<PluginRow[]>([]);
  const [summary, setSummary] = useState<Summary>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch<{ plugins?: PluginRow[]; summary?: Summary }>("/marketplace/plugins");
      const plugins = data.plugins ?? [];
      const sum = data.summary ?? {};
      setSummary(sum);
      setInstalled(plugins.filter((p) => p.installed));
      setAvailable(plugins.filter((p) => !p.installed));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load plugins");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const mutate = async (action: "install" | "uninstall", pluginId: string) => {
    setBusy(pluginId);
    try {
      await apiFetch(`/marketplace/${action}`, {
        method: "POST",
        body: JSON.stringify({ plugin_id: pluginId }),
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      <p className="rounded-lg border border-border/60 bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
        <strong className="text-foreground">Runtime plugins</strong> extend operational capability (deploy, repair, provider hooks).
        For AI execution skills, use the{" "}
        <Link href="/mission-control/marketplace" className="underline">
          Skill marketplace
        </Link>
        .
      </p>
      <header className="border-b border-border/60 pb-6">
        <h1 className="text-xl font-semibold tracking-tight">Runtime plugins</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Installed extensions, health, and permissions — operational, not a storefront.
        </p>
        {summary.plugin_health ? (
          <p className="mt-2 text-xs text-muted-foreground">
            {summary.installed_count ?? 0} installed · {summary.plugin_health.healthy_count ?? 0} healthy
            {(summary.plugin_health.failed_count ?? 0) > 0 ? ` · ${summary.plugin_health.failed_count} failed` : ""}
          </p>
        ) : null}
      </header>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <section className="space-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Installed</h2>
        <ul className="space-y-2">
          {installed.map((p) => (
            <li
              key={p.plugin_id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/50 bg-card/40 px-4 py-3 text-sm"
            >
              <div>
                <span className="font-medium">{p.name ?? p.plugin_id}</span>
                <span className="ml-2 font-mono text-xs text-muted-foreground">{p.version}</span>
                <span className="ml-2 text-xs capitalize text-muted-foreground">{p.runtime_state}</span>
              </div>
              <button
                type="button"
                disabled={busy === p.plugin_id}
                className="rounded border border-border px-2 py-1 text-xs hover:bg-muted/50 disabled:opacity-50"
                onClick={() => void mutate("uninstall", p.plugin_id)}
              >
                Uninstall
              </button>
            </li>
          ))}
          {!installed.length ? <li className="text-sm text-muted-foreground">No plugins installed.</li> : null}
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Available</h2>
        <ul className="space-y-2">
          {available.map((p) => (
            <li
              key={p.plugin_id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/50 px-4 py-3 text-sm"
            >
              <div>
                <span className="font-medium">{p.name ?? p.plugin_id}</span>
                <span className="ml-2 text-xs text-muted-foreground">{p.trust_tier}</span>
                {p.permissions?.length ? (
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">{p.permissions.join(", ")}</p>
                ) : null}
              </div>
              <button
                type="button"
                disabled={busy === p.plugin_id}
                className="rounded bg-primary/90 px-2 py-1 text-xs text-primary-foreground hover:bg-primary disabled:opacity-50"
                onClick={() => void mutate("install", p.plugin_id)}
              >
                Install
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
