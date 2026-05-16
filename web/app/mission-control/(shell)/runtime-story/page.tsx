"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type Payload = {
  runtime_storyline?: { chapter?: string; text?: string }[];
  strategic_operational_journey?: { current_chapter?: string; era_count?: number };
  operational_narratives_v2?: { shifts?: string[]; continuity_story?: string };
};

export default function RuntimeStoryPage() {
  const [data, setData] = useState<Payload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await apiFetch<Payload>("/mission-control/runtime-story"));
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
        <h1 className="text-xl font-semibold">Runtime story</h1>
        <p className="mt-1 text-sm text-muted-foreground">Operational narrative — what changed and why it matters</p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {data.operational_narratives_v2?.continuity_story ? (
        <p className="text-sm text-muted-foreground">{data.operational_narratives_v2.continuity_story}</p>
      ) : null}
      <ul className="space-y-3 text-sm">
        {(data.runtime_storyline ?? []).map((s, i) => (
          <li key={i} className="border-b border-border/30 pb-2">
            <span className="text-xs uppercase text-muted-foreground">{s.chapter}</span>
            <p className="mt-1">{s.text}</p>
          </li>
        ))}
      </ul>
      <Link href="/mission-control/runtime-overview" className="text-sm text-primary hover:underline">
        Runtime overview
      </Link>
    </div>
  );
}
