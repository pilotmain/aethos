/**
 * Phase 73b — Self-Improvement (Genesis Loop) typed web client.
 *
 * Wraps `/api/v1/self_improvement/*`:
 *   - GET  /                                — list proposals
 *   - GET  /{id}                            — proposal detail
 *   - POST /propose                         — generate + validate + persist
 *   - POST /{id}/sandbox                    — run in isolated git worktree
 *   - POST /{id}/approve | /reject          — flip status
 *   - POST /{id}/apply                      — apply diff + local commit
 *   - POST /{id}/revert                     — git revert previously applied
 *
 * The API itself is gated by `NEXA_SELF_IMPROVEMENT_ENABLED` (default off);
 * when disabled every endpoint returns 404 — UIs should detect this and
 * render a "feature disabled" empty state.
 */

import { apiFetch } from "@/lib/api/client";

export type SelfImprovementStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "applied"
  | "reverted"
  | "pr_open"
  | "merged"
  | "revert_pr_open";

export type SandboxStep = {
  name: string;
  cmd: string[];
  exit_code: number;
  duration_s: number;
  stdout_tail: string;
  stderr_tail: string;
  timed_out: boolean;
};

export type SandboxResult = {
  proposal_id: string;
  success: boolean;
  worktree_path: string;
  started_at: number;
  duration_s: number;
  error: string | null;
  steps: SandboxStep[];
};

export type SelfImprovementProposal = {
  id: string;
  title: string;
  problem_statement: string;
  target_paths: string[];
  diff: string;
  status: SelfImprovementStatus;
  rationale: string | null;
  created_by: string | null;
  created_at: string;
  sandbox_result: SandboxResult | null;
  applied_commit_sha: string | null;
  reverted_commit_sha: string | null;
  pr_number: number | null;
  pr_url: string | null;
  github_branch: string | null;
  merge_commit_sha: string | null;
  revert_pr_number: number | null;
  revert_pr_url: string | null;
};

export type SelfImprovementCapabilities = {
  ok: boolean;
  self_improvement: {
    enabled: boolean;
    max_files_per_proposal: number;
    max_diff_lines: number;
    allowed_paths: string;
  };
  github: {
    enabled: boolean;
    configured: boolean;
    owner: string | null;
    repo: string | null;
    base_branch: string | null;
    branch_prefix: string | null;
    merge_method: string | null;
  };
  auto_restart: {
    enabled: boolean;
    deferred: string;
  };
};

export type OpenPrResponse = {
  ok: boolean;
  proposal: SelfImprovementProposal;
  pr: {
    number: number;
    url: string;
    head_branch: string;
    base_branch: string;
    head_sha: string;
  };
};

export type PrStatusResponse = {
  ok: boolean;
  pr: {
    number: number;
    state: string;
    merged: boolean;
    mergeable: boolean | null;
    mergeable_state: string | null;
    head_sha: string | null;
    head_branch: string;
    base_branch: string;
  };
};

export type MergePrResponse = {
  ok: boolean;
  proposal: SelfImprovementProposal;
  merge_commit_sha?: string;
  note?: string;
};

export type RevertMergeResponse = {
  ok: boolean;
  proposal: SelfImprovementProposal;
  revert_pr: {
    number: number;
    url: string;
    head_branch: string;
    base_branch: string;
  };
};

export type ValidationFile = {
  path: string;
  added_lines: number;
  removed_lines: number;
  is_new: boolean;
  is_delete: boolean;
};

export type ValidationSummary = {
  errors: string[];
  warnings: string[];
  files: ValidationFile[];
  total_added: number;
  total_removed: number;
};

export type ListProposalsResponse = {
  ok: boolean;
  proposals: SelfImprovementProposal[];
};

export type ProposalDetailResponse = {
  ok: boolean;
  proposal: SelfImprovementProposal;
};

export type ProposeResponse = {
  ok: boolean;
  proposal?: SelfImprovementProposal;
  validation: ValidationSummary;
  diff_preview?: string;
};

export type SandboxResponse = {
  ok: boolean;
  sandbox: SandboxResult;
  proposal: SelfImprovementProposal;
};

export type ApplyResponse = {
  ok: boolean;
  proposal: SelfImprovementProposal;
  applied_commit_sha: string | null;
  note: string;
};

export type RevertResponse = {
  ok: boolean;
  proposal: SelfImprovementProposal;
  reverted_commit_sha: string | null;
};

export async function listSelfImprovementProposals(
  statusFilter?: SelfImprovementStatus,
  limit = 50,
): Promise<ListProposalsResponse> {
  const q = new URLSearchParams();
  if (statusFilter) q.set("status_filter", statusFilter);
  q.set("limit", String(limit));
  return apiFetch<ListProposalsResponse>(`/self_improvement/?${q}`);
}

export async function getSelfImprovementProposal(
  id: string,
): Promise<ProposalDetailResponse> {
  return apiFetch<ProposalDetailResponse>(
    `/self_improvement/${encodeURIComponent(id)}`,
  );
}

export async function proposeSelfImprovement(body: {
  title: string;
  problem_statement: string;
  target_paths: string[];
  extra_context_paths?: string[];
  rationale?: string | null;
}): Promise<ProposeResponse> {
  return apiFetch<ProposeResponse>(`/self_improvement/propose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: body.title,
      problem_statement: body.problem_statement,
      target_paths: body.target_paths,
      extra_context_paths: body.extra_context_paths ?? [],
      rationale: body.rationale ?? null,
    }),
  });
}

export async function runSelfImprovementSandbox(
  id: string,
  pytestTargets?: string[],
): Promise<SandboxResponse> {
  return apiFetch<SandboxResponse>(
    `/self_improvement/${encodeURIComponent(id)}/sandbox`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pytest_targets: pytestTargets ?? null }),
    },
  );
}

export async function approveSelfImprovement(
  id: string,
): Promise<ProposalDetailResponse> {
  return apiFetch<ProposalDetailResponse>(
    `/self_improvement/${encodeURIComponent(id)}/approve`,
    { method: "POST" },
  );
}

export async function rejectSelfImprovement(
  id: string,
): Promise<ProposalDetailResponse> {
  return apiFetch<ProposalDetailResponse>(
    `/self_improvement/${encodeURIComponent(id)}/reject`,
    { method: "POST" },
  );
}

export async function applySelfImprovement(id: string): Promise<ApplyResponse> {
  return apiFetch<ApplyResponse>(
    `/self_improvement/${encodeURIComponent(id)}/apply`,
    { method: "POST" },
  );
}

export async function revertSelfImprovement(
  id: string,
): Promise<RevertResponse> {
  return apiFetch<RevertResponse>(
    `/self_improvement/${encodeURIComponent(id)}/revert`,
    { method: "POST" },
  );
}

// --- Phase 73c: GitHub auto-merge flow ---------------------------------

export async function selfImprovementCapabilities(): Promise<SelfImprovementCapabilities> {
  return apiFetch<SelfImprovementCapabilities>(`/self_improvement/-/capabilities`);
}

export async function openSelfImprovementPr(id: string): Promise<OpenPrResponse> {
  return apiFetch<OpenPrResponse>(
    `/self_improvement/${encodeURIComponent(id)}/open-pr`,
    { method: "POST" },
  );
}

export async function getSelfImprovementPrStatus(
  id: string,
): Promise<PrStatusResponse> {
  return apiFetch<PrStatusResponse>(
    `/self_improvement/${encodeURIComponent(id)}/pr-status`,
  );
}

export async function mergeSelfImprovementPr(
  id: string,
): Promise<MergePrResponse> {
  return apiFetch<MergePrResponse>(
    `/self_improvement/${encodeURIComponent(id)}/merge-pr`,
    { method: "POST" },
  );
}

export async function revertSelfImprovementMerge(
  id: string,
): Promise<RevertMergeResponse> {
  return apiFetch<RevertMergeResponse>(
    `/self_improvement/${encodeURIComponent(id)}/revert-merge`,
    { method: "POST" },
  );
}
