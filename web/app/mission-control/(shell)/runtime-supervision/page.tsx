"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { fetchPanelResilient, formatOperationalError } from "@/lib/runtimeResilience";

type SupervisionPayload = {
  runtime_supervision?: {
    api_owner_status?: string;
    sqlite_status?: string;
    telegram_mode?: string;
    hydration_lock_clear?: boolean;
    degraded_mode?: boolean;
    ownership_authoritative?: boolean;
    process_conflicts?: number;
    operator_summary?: string;
    recommended_repairs?: string[];
  };
  telegram_ownership?: { message?: string };
};

export default function RuntimeSupervisionPage() {
  const [data, setData] = useState<SupervisionPayload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const r = await fetchPanelResilient<SupervisionPayload>("/runtime/supervision", {});
    setData(r.data);
    setError(r.error ? formatOperationalError(r.error) : null);
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 10000);
    return () => clearInterval(t);
  }, [refresh]);

  const sup = data.runtime_supervision ?? {};

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Runtime supervision</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Ownership, SQLite, Telegram, and startup coordination
        </p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {sup.degraded_mode ? (
        <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm">
          Runtime supervision reports degraded or observer mode.
        </p>
      ) : null}
      <section className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">API owner</p>
          <p className="mt-1 text-lg font-medium capitalize">{sup.api_owner_status ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">SQLite</p>
          <p className="mt-1 text-lg font-medium capitalize">{sup.sqlite_status ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Telegram</p>
          <p className="mt-1 text-sm">{data.telegram_ownership?.message ?? sup.telegram_mode ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Hydration lock</p>
          <p className="mt-1 text-lg font-medium">{sup.hydration_lock_clear ? "clear" : "active"}</p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Ownership authority</p>
          <p className="mt-1 text-lg font-medium">
            {sup.ownership_authoritative ? "authoritative" : "coordinating"}
          </p>
        </div>
        <div className="rounded-lg border border-border/50 px-4 py-3">
          <p className="text-xs uppercase text-muted-foreground">Process conflicts</p>
          <p className="mt-1 text-lg font-medium">{sup.process_conflicts ?? 0}</p>
        </div>
      </section>
      {sup.operator_summary ? (
        <pre className="whitespace-pre-wrap rounded-lg border border-border/50 bg-muted/30 p-4 text-sm">
          {sup.operator_summary}
        </pre>
      ) : null}
      <Link href="/mission-control/runtime-recovery" className="text-sm underline">
        Runtime recovery center
      </Link>
    </div>
  );
}
