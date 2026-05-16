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
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState("");

  const refresh = useCallback(async () => {
    try {
      const path =
        query.trim().length > 0
          ? `/mission-control/governance/search?q=${encodeURIComponent(query.trim())}`
          : kindFilter
            ? `/mission-control/governance/filter?kind=${encodeURIComponent(kindFilter)}`
            : "/mission-control/timeline/window?limit=32";
      const g = await apiFetch<{ timeline?: TimelineEntry[]; entries?: TimelineEntry[] }>(path);
      setTimeline(g.timeline ?? g.entries ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, [query, kindFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Governance</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Searchable operational timeline — bounded windows under load
        </p>
      </header>
      <div className="flex flex-wrap gap-2">
        <input
          className="min-w-[12rem] flex-1 rounded-md border border-border/50 bg-background px-3 py-2 text-sm"
          placeholder="Search governance…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void refresh()}
        />
        <select
          className="rounded-md border border-border/50 bg-background px-2 py-2 text-sm"
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
        >
          <option value="">All kinds</option>
          <option value="provider">Provider</option>
          <option value="deployment">Deployment</option>
          <option value="privacy">Privacy</option>
          <option value="repair">Repair</option>
          <option value="deliverable">Deliverable</option>
        </select>
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
          onClick={() => void refresh()}
        >
          Apply
        </button>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <ul className="space-y-3 text-sm">
        {timeline.map((e, i) => (
          <li key={i} className="border-b border-border/30 pb-2">
            <span className="text-xs text-muted-foreground">
              {e.at ?? "—"} · {e.kind}
            </span>
            <p className="mt-1">{e.what}</p>
            <p className="text-xs text-muted-foreground">
              {e.who}
              {e.privacy_mode ? ` · privacy ${e.privacy_mode}` : ""}
            </p>
          </li>
        ))}
        {!timeline.length && !error ? (
          <li className="text-muted-foreground">No governance events yet.</li>
        ) : null}
      </ul>
    </div>
  );
}
