"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type TimelineEntry = {
  at?: string;
  kind?: string;
  who?: string;
  what?: string;
  privacy_mode?: string | null;
};

export default function GovernancePage() {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const g = await apiFetch<{ timeline?: TimelineEntry[] }>("/mission-control/governance");
      setTimeline(g.timeline ?? []);
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
        <h1 className="text-xl font-semibold">Governance</h1>
        <p className="mt-1 text-sm text-muted-foreground">Operational timeline — what changed and through which provider or plugin</p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <ul className="space-y-3 text-sm">
        {timeline.map((e, i) => (
          <li key={i} className="border-b border-border/30 pb-2">
            <span className="text-xs text-muted-foreground">{e.at ?? "—"} · {e.kind}</span>
            <p className="mt-1">{e.what}</p>
            <p className="text-xs text-muted-foreground">{e.who}{e.privacy_mode ? ` · privacy ${e.privacy_mode}` : ""}</p>
          </li>
        ))}
        {!timeline.length && !error ? <li className="text-muted-foreground">No governance events yet.</li> : null}
      </ul>
    </div>
  );
}
