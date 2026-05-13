"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatMissionControlApiError } from "@/lib/api";
import { apiFetch } from "@/lib/api/client";

type AuditEvent = {
  timestamp?: string;
  user_id?: string;
  action?: string;
  outcome?: string;
  details?: Record<string, unknown>;
};

type RecentResponse = {
  ok?: boolean;
  enabled?: boolean;
  dir?: string;
  events?: AuditEvent[];
};

function downloadCsv(rows: AuditEvent[]) {
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  const lines = [
    ["timestamp", "user_id", "action", "outcome", "details_json"].map(esc).join(","),
    ...rows.map((r) =>
      [
        r.timestamp,
        r.user_id,
        r.action,
        r.outcome,
        JSON.stringify(r.details ?? {}),
      ]
        .map(esc)
        .join(","),
    ),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `aethos-enterprise-audit-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function EnterpriseAuditPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<RecentResponse | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [days, setDays] = useState(7);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const j = await apiFetch<RecentResponse>(`/enterprise-audit/recent?days=${days}&limit=500`);
      setData(j);
    } catch (e) {
      setData(null);
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  const events = useMemo(() => (Array.isArray(data?.events) ? data!.events! : []), [data]);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Audit logs (JSONL)</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Structured events from the API host (gateway turns, SSO callbacks). Owner-gated; complements the
          governance DB export under Approvals / governance tools.
        </p>
      </div>

      <Card className="border-zinc-800 bg-zinc-900/40">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg text-zinc-100">Filters</CardTitle>
          <CardDescription className="text-zinc-500">Recent days window (UTC day files).</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm text-zinc-400">
            Days
            <select
              className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-zinc-100"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            >
              {[1, 3, 7, 14, 30, 90].map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          <Button type="button" variant="secondary" onClick={() => void load()} disabled={loading}>
            {loading ? "Loading…" : "Refresh"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="border-zinc-600 text-zinc-200"
            disabled={!events.length}
            onClick={() => downloadCsv(events)}
          >
            Download CSV
          </Button>
        </CardContent>
      </Card>

      {data?.dir && (
        <p className="text-xs text-zinc-500">
          Directory: <code className="text-zinc-400">{data.dir}</code>
        </p>
      )}

      {error && (
        <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200" role="alert">
          {error}
        </div>
      )}

      {data && data.enabled === false && (
        <p className="text-sm text-amber-200/90">File audit is disabled (AUDIT_ENABLED=false on the API).</p>
      )}

      <Card className="border-zinc-800 bg-zinc-900/40">
        <CardHeader>
          <CardTitle className="text-lg text-zinc-100">Events</CardTitle>
          <CardDescription className="text-zinc-500">{events.length} row(s) loaded.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {loading && <p className="text-sm text-zinc-500">Loading…</p>}
          {!loading && !events.length && <p className="text-sm text-zinc-500">No events in range.</p>}
          {events.map((ev, i) => {
            const open = expanded[i];
            return (
              <div key={`${ev.timestamp}-${i}`} className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-mono text-xs text-zinc-500">{ev.timestamp || "—"}</span>
                  <Badge variant="outline" className="border-zinc-600 text-zinc-200">
                    {ev.action || "?"}
                  </Badge>
                  <Badge variant="secondary" className="bg-zinc-800 text-zinc-200">
                    {ev.outcome || "?"}
                  </Badge>
                  <span className="truncate font-mono text-xs text-zinc-400">{ev.user_id || ""}</span>
                </div>
                <button
                  type="button"
                  className="mt-2 text-xs text-violet-300 hover:text-violet-200"
                  onClick={() => setExpanded((prev) => ({ ...prev, [i]: !prev[i] }))}
                >
                  {open ? "Hide details" : "Show JSON"}
                </button>
                {open && (
                  <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-black/40 p-2 text-[11px] text-emerald-100/90">
                    {JSON.stringify(ev.details ?? {}, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
