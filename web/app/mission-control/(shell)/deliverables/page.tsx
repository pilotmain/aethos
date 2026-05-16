"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type DeliverableRow = {
  deliverable_id?: string;
  title?: string;
  type?: string;
  summary?: string;
  status?: string;
  worker_handle?: string;
  task_id?: string;
  created_at?: string;
  privacy_metadata?: { redacted?: boolean; pii_categories?: string[] };
};

type DeliverablesPayload = {
  deliverables?: DeliverableRow[];
};

export default function DeliverablesPage() {
  const [rows, setRows] = useState<DeliverableRow[]>([]);
  const [q, setQ] = useState("");
  const [dtype, setDtype] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      if (dtype) params.set("type", dtype);
      params.set("limit", "24");
      const path = `/mission-control/deliverables${params.toString() ? `?${params}` : ""}`;
      const data = await apiFetch<DeliverablesPayload>(path);
      setRows(data.deliverables ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load deliverables");
    }
  }, [q, dtype]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const exportOne = async (id: string, format: string) => {
    const data = await apiFetch<{ body?: string }>(
      `/mission-control/deliverables/${encodeURIComponent(id)}/export?format=${format}`,
    );
    const blob = new Blob([data.body ?? ""], {
      type: format === "json" ? "application/json" : "text/plain",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${id}.${format === "json" ? "json" : format === "text" ? "txt" : "md"}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Deliverables</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Runtime-backed worker outputs — search, filter, export
        </p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <input
          className="min-w-[200px] flex-1 rounded border border-border/60 bg-background px-3 py-2 text-sm"
          placeholder="Search summaries…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void refresh()}
        />
        <select
          className="rounded border border-border/60 bg-background px-3 py-2 text-sm"
          value={dtype}
          onChange={(e) => setDtype(e.target.value)}
        >
          <option value="">All types</option>
          <option value="research_summary">Research</option>
          <option value="deployment_report">Deployment</option>
          <option value="repair_summary">Repair</option>
          <option value="verification_report">Verification</option>
        </select>
        <button
          type="button"
          className="rounded bg-primary px-4 py-2 text-sm text-primary-foreground"
          onClick={() => void refresh()}
        >
          Search
        </button>
      </div>
      <ul className="space-y-3">
        {rows.length === 0 ? (
          <li className="text-sm text-muted-foreground">No deliverables yet.</li>
        ) : (
          rows.map((r) => (
            <li
              key={r.deliverable_id}
              className="rounded border border-border/50 p-4 text-sm space-y-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{r.title ?? r.type}</span>
                <span className="text-xs text-muted-foreground">{r.status}</span>
              </div>
              <p className="text-muted-foreground line-clamp-2">{r.summary}</p>
              <p className="text-xs text-muted-foreground">
                {r.worker_handle ? `@${r.worker_handle}` : ""} · {r.task_id ?? "—"} ·{" "}
                {r.created_at?.slice(0, 19) ?? ""}
                {r.privacy_metadata?.redacted ? " · redacted" : ""}
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="text-xs underline"
                  onClick={() => r.deliverable_id && void exportOne(r.deliverable_id, "markdown")}
                >
                  Export MD
                </button>
                <button
                  type="button"
                  className="text-xs underline"
                  onClick={() => r.deliverable_id && void exportOne(r.deliverable_id, "json")}
                >
                  Export JSON
                </button>
              </div>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
