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
import {
  cancelJob,
  decideJob,
  fetchPendingApprovals,
  type ApprovalDecision,
  type PendingApproval,
} from "@/lib/api/approvals";

type RowState = {
  busy: boolean;
  error: string | null;
};

const RISK_VARIANT: Record<
  string,
  "default" | "secondary" | "outline" | "success" | "warning" | "muted"
> = {
  high: "warning",
  medium: "default",
  low: "secondary",
  blocked: "warning",
  normal: "secondary",
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString();
  } catch {
    return value;
  }
}

export default function MissionControlApprovalsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [rowState, setRowState] = useState<Record<number, RowState>>({});

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchPendingApprovals();
      setApprovals(rows);
    } catch (e) {
      setApprovals([]);
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const setBusy = (id: number, busy: boolean, errMsg: string | null = null) => {
    setRowState((prev) => ({ ...prev, [id]: { busy, error: errMsg } }));
  };

  const handleDecision = useCallback(
    async (id: number, decision: ApprovalDecision) => {
      setBusy(id, true);
      try {
        await decideJob(id, decision);
        await reload();
      } catch (e) {
        setBusy(
          id,
          false,
          formatMissionControlApiError(e instanceof Error ? e.message : String(e)),
        );
      }
    },
    [reload],
  );

  const handleCancel = useCallback(
    async (id: number) => {
      setBusy(id, true);
      try {
        await cancelJob(id);
        await reload();
      } catch (e) {
        setBusy(
          id,
          false,
          formatMissionControlApiError(e instanceof Error ? e.message : String(e)),
        );
      }
    },
    [reload],
  );

  const summary = useMemo(() => {
    const total = approvals.length;
    const high = approvals.filter((a) => (a.risk_level || "").toLowerCase() === "high").length;
    return { total, high };
  }, [approvals]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-50">Pending approvals</h1>
        <p className="mt-1 text-sm text-zinc-400">
          High-risk and gated agent jobs waiting for human sign-off. Approve or deny here, or do it
          from Telegram — both surfaces share the same <code>agent_jobs.awaiting_approval</code>{" "}
          state.
        </p>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 text-xs text-zinc-400">
        <Badge variant="secondary">{summary.total} pending</Badge>
        {summary.high ? (
          <Badge variant="warning">{summary.high} high-risk</Badge>
        ) : null}
        <Button
          size="sm"
          variant="outline"
          onClick={() => void reload()}
          disabled={loading}
          className="ml-auto"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      {loading && approvals.length === 0 ? (
        <div className="flex h-48 items-center justify-center">
          <div className="text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
            <p className="mt-2 text-sm text-zinc-500">Loading pending approvals…</p>
          </div>
        </div>
      ) : approvals.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-zinc-400">
            Nothing waiting on you. New high-risk actions appear here automatically.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {approvals.map((approval) => {
            const state = rowState[approval.id] || { busy: false, error: null };
            const riskKey = (approval.risk_level || "").toLowerCase();
            const riskVariant = RISK_VARIANT[riskKey] || "outline";
            return (
              <Card key={approval.id}>
                <CardHeader>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <CardTitle className="text-base">
                        #{approval.id} — {approval.title}
                      </CardTitle>
                      <CardDescription className="flex flex-wrap items-center gap-2">
                        <span>kind: {approval.kind}</span>
                        <span>•</span>
                        <span>worker: {approval.worker_type}</span>
                        {approval.host_action ? (
                          <>
                            <span>•</span>
                            <span>action: {approval.host_action}</span>
                          </>
                        ) : null}
                        {approval.target ? (
                          <>
                            <span>•</span>
                            <span>target: {approval.target}</span>
                          </>
                        ) : null}
                      </CardDescription>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {approval.risk_level ? (
                        <Badge variant={riskVariant}>risk: {approval.risk_level}</Badge>
                      ) : null}
                      {approval.status ? (
                        <Badge variant="outline">{approval.status}</Badge>
                      ) : null}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {approval.description ? (
                    <p className="text-sm text-zinc-300 whitespace-pre-wrap">
                      {approval.description}
                    </p>
                  ) : null}

                  {Object.keys(approval.payload_preview || {}).length > 0 ? (
                    <details className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3 text-xs text-zinc-400">
                      <summary className="cursor-pointer text-zinc-300">Payload preview</summary>
                      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all text-zinc-300">
                        {JSON.stringify(approval.payload_preview, null, 2)}
                      </pre>
                    </details>
                  ) : null}

                  <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500">
                    <span>Requested {formatDate(approval.created_at)}</span>
                    {approval.started_at ? (
                      <>
                        <span>•</span>
                        <span>Started {formatDate(approval.started_at)}</span>
                      </>
                    ) : null}
                  </div>

                  {state.error ? (
                    <div className="rounded border border-red-900/50 bg-red-950/40 px-3 py-2 text-xs text-red-200">
                      {state.error}
                    </div>
                  ) : null}

                  <div className="flex flex-wrap gap-2 pt-1">
                    <Button
                      size="sm"
                      onClick={() => void handleDecision(approval.id, "approved")}
                      disabled={state.busy}
                    >
                      {state.busy ? "Working…" : "Approve"}
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => void handleDecision(approval.id, "denied")}
                      disabled={state.busy}
                    >
                      Deny
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void handleCancel(approval.id)}
                      disabled={state.busy}
                    >
                      Cancel job
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
