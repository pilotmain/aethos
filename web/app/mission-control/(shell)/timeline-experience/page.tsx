"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type Window = { kind?: string; count?: number; preview?: { what?: string } };
type Payload = {
  timeline_experience?: { headline?: string; entry_count?: number };
  governance_story_windows?: Window[];
  operational_era_summaries?: { label?: string; summary?: string }[];
};

export default function TimelineExperiencePage() {
  const [data, setData] = useState<Payload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await apiFetch<Payload>("/mission-control/timeline-experience"));
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
        <h1 className="text-xl font-semibold">Timeline experience</h1>
        <p className="mt-1 text-sm text-muted-foreground">Grouped governance windows — calm operational history</p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <ul className="space-y-3 text-sm">
        {(data.governance_story_windows ?? []).map((w, i) => (
          <li key={i} className="rounded border border-border/40 px-3 py-2">
            <span className="font-medium capitalize">{w.kind}</span>
            <span className="text-muted-foreground"> · {w.count} events</span>
            {w.preview?.what ? <p className="mt-1 text-muted-foreground">{w.preview.what}</p> : null}
          </li>
        ))}
      </ul>
      <Link href="/mission-control/governance" className="text-sm text-primary hover:underline">
        Governance timeline
      </Link>
    </div>
  );
}
