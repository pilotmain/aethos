"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type Payload = {
  enterprise_operational_story?: string;
  executive_operational_overview?: Record<string, unknown>;
  strategic_runtime_summary?: { outlook?: string; trajectory?: string };
};

export default function ExecutiveOverviewPage() {
  const [data, setData] = useState<Payload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await apiFetch<Payload>("/mission-control/executive-overview"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const exec = data.executive_operational_overview as Record<string, unknown> | undefined;
  const strategic = data.strategic_runtime_summary;

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Executive overview</h1>
        <p className="mt-1 text-sm text-muted-foreground">Strategic runtime posture — summary-first and calm</p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {data.enterprise_operational_story ? (
        <p className="rounded-lg border border-border/40 bg-card/30 px-4 py-3 text-sm">{data.enterprise_operational_story}</p>
      ) : null}
      {strategic?.outlook || strategic?.trajectory ? (
        <p className="text-sm text-muted-foreground">
          {strategic.outlook ? `Outlook: ${strategic.outlook}` : null}
          {strategic.trajectory ? ` · Trajectory: ${strategic.trajectory}` : null}
        </p>
      ) : null}
      {exec ? (
        <pre className="overflow-x-auto rounded-lg border border-border/40 bg-card/20 p-3 text-xs text-muted-foreground">
          {JSON.stringify(exec, null, 2).slice(0, 2000)}
        </pre>
      ) : null}
      <Link href="/mission-control/runtime-overview" className="text-sm text-primary hover:underline">
        Runtime overview
      </Link>
    </div>
  );
}
