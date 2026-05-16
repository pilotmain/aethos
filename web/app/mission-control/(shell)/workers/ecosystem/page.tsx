"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type Payload = {
  worker_collaboration_story?: string;
  worker_contribution_highlights?: string[];
  lifecycle_storytelling?: { journey?: string; maturity_level?: string };
};

export default function WorkerEcosystemPage() {
  const [data, setData] = useState<Payload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await apiFetch<Payload>("/mission-control/workers/ecosystem"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Worker ecosystem</h1>
        <p className="mt-1 text-sm text-muted-foreground">Orchestrator-led specialists — lifecycle and trust</p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {data.worker_collaboration_story ? (
        <p className="rounded-lg border border-border/40 bg-card/30 px-4 py-3 text-sm">{data.worker_collaboration_story}</p>
      ) : null}
      {data.lifecycle_storytelling?.journey ? (
        <p className="text-sm text-muted-foreground">Lifecycle: {data.lifecycle_storytelling.journey}</p>
      ) : null}
      {data.worker_contribution_highlights?.length ? (
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {data.worker_contribution_highlights.map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ul>
      ) : null}
      <Link href="/mission-control/office" className="text-sm text-primary hover:underline">
        Office
      </Link>
    </div>
  );
}
