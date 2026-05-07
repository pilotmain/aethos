"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMissionControlApiError } from "@/lib/api";
import {
  fetchAgentAssignments,
  groupAssignmentsByAgent,
  isAssignmentTerminal,
  summarizeAssignments,
  type AgentAssignmentRow,
} from "@/lib/api/assignments";

const RUNNING_STATUSES = new Set(["running", "queued", "assigned", "waiting_worker", "waiting_approval"]);

function statusBadgeVariant(status: string): "default" | "secondary" | "outline" | "success" | "warning" | "muted" {
  const s = (status || "").toLowerCase();
  if (s === "completed") return "success";
  if (s === "failed") return "warning";
  if (s === "cancelled") return "muted";
  if (RUNNING_STATUSES.has(s)) return "default";
  return "secondary";
}

export function AssignmentsByAgentPanel() {
  const [rows, setRows] = useState<AgentAssignmentRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchAgentAssignments()
      .then((data) => {
        if (cancelled) return;
        setRows(data);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setRows([]);
        setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const summary = summarizeAssignments(rows);
  const grouped = groupAssignmentsByAgent(rows);
  const handles = Object.keys(grouped).sort((a, b) => a.localeCompare(b));

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">Agent assignments</CardTitle>
            <CardDescription>
              Live work delegated to agents (POST <code className="font-mono">/api/v1/agent-assignments</code> auto-runs
              <code className="ml-1 font-mono">dispatch_assignment</code> when{" "}
              <code className="font-mono">NEXA_ASSIGNMENT_AUTO_DISPATCH_DEFAULT=true</code>).
            </CardDescription>
          </div>
          <div className="flex shrink-0 flex-wrap gap-1">
            <Badge variant="secondary">Total {summary.total}</Badge>
            <Badge variant="default">Running {summary.running}</Badge>
            <Badge variant="success">Done {summary.completed}</Badge>
            <Badge variant="warning">Failed {summary.failed}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="rounded-md border border-amber-900/60 bg-amber-950/40 px-3 py-2 text-sm text-amber-100">
            {error}
          </div>
        ) : loading ? (
          <p className="text-sm text-zinc-500">Loading agent assignments…</p>
        ) : handles.length === 0 ? (
          <p className="text-sm text-zinc-500">
            No agent assignments yet. Create one with{" "}
            <code className="font-mono">POST /api/v1/agent-assignments</code> or via the chat UI.
          </p>
        ) : (
          <ul className="space-y-3">
            {handles.map((handle) => {
              const items = grouped[handle];
              return (
                <li key={handle} className="rounded-md border border-zinc-800 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="font-mono text-sm text-zinc-100">@{handle}</span>
                    <Badge variant="outline">{items.length}</Badge>
                  </div>
                  <ul className="space-y-1.5">
                    {items.slice(0, 8).map((row) => (
                      <li key={row.id} className="flex items-start justify-between gap-2 text-sm">
                        <span className="line-clamp-2 text-zinc-200">{row.title || `Assignment #${row.id}`}</span>
                        <Badge variant={statusBadgeVariant(row.status)}>
                          {isAssignmentTerminal(row.status) ? row.status : row.status || "queued"}
                        </Badge>
                      </li>
                    ))}
                    {items.length > 8 ? (
                      <li className="text-xs text-zinc-500">+{items.length - 8} more</li>
                    ) : null}
                  </ul>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
