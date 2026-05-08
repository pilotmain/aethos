/**
 * Phase 70 — Mission Control "Pending Approvals" client.
 *
 * Wraps:
 *   - GET  /api/v1/approvals/pending          — list agent_jobs awaiting approval
 *   - POST /api/v1/web/jobs/{id}/decision     — approve / deny via the web proxy
 *   - POST /api/v1/web/jobs/{id}/cancel       — cancel a pending job via the web proxy
 *
 * Approve / deny / cancel deliberately reuse the existing web proxies so
 * Telegram approvals and the web panel stay on a single source of truth
 * (``agent_jobs.awaiting_approval``).
 */

import { apiFetch } from "@/lib/api/client";

export type PendingApproval = {
  id: number;
  title: string;
  description: string;
  kind: string;
  worker_type: string;
  command_type: string | null;
  host_action: string | null;
  target: string | null;
  risk_level: string | null;
  status: string;
  created_at: string | null;
  started_at: string | null;
  approval_decision: string | null;
  approval_context: Record<string, unknown> | null;
  payload_preview: Record<string, unknown>;
};

export type PendingApprovalsResponse = {
  approvals: PendingApproval[];
  count: number;
  limit: number;
};

export type ApprovalDecision = "approved" | "denied";

export async function fetchPendingApprovals(limit = 50): Promise<PendingApproval[]> {
  const safe = Math.max(1, Math.min(Math.trunc(limit) || 50, 200));
  const data = await apiFetch<PendingApprovalsResponse>(
    `/approvals/pending?limit=${safe}`,
  );
  return Array.isArray(data?.approvals) ? data.approvals : [];
}

export async function decideJob(
  jobId: number,
  decision: ApprovalDecision,
): Promise<{ id: number; status: string }> {
  return apiFetch<{ id: number; status: string }>(
    `/web/jobs/${encodeURIComponent(String(jobId))}/decision`,
    {
      method: "POST",
      body: JSON.stringify({ decision }),
    },
  );
}

export async function cancelJob(jobId: number): Promise<{ id: number; status: string }> {
  return apiFetch<{ id: number; status: string }>(
    `/web/jobs/${encodeURIComponent(String(jobId))}/cancel`,
    { method: "POST" },
  );
}
