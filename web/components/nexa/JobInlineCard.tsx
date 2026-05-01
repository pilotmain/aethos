"use client";

import { useMemo, useState } from "react";
import type { NexaJob } from "@/lib/nexa-types";
import { jobNeedsBadge } from "@/lib/suggestions";
import { webFetch } from "@/lib/api";

const DEV_AGENT = "dev_executor";

type Props = {
  job: NexaJob;
  onUpdated?: (j: NexaJob) => void;
  onNotify?: (message: string) => void;
  compact?: boolean;
};

function riskTone(r: string | null | undefined) {
  const l = (r || "").toLowerCase();
  if (l === "low") {
    return "text-emerald-300/90";
  }
  if (l === "high") {
    return "text-rose-300/90";
  }
  if (l === "medium" || l === "normal" || l === "med") {
    return "text-amber-300/90";
  }
  return "text-zinc-300";
}

export function JobInlineCard({ job, onUpdated, onNotify, compact }: Props) {
  const [loading, setLoading] = useState<"ap" | "den" | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const isHost = (job.command_type || "").toLowerCase() === "host-executor";
  const hostPayload = job.payload_json as {
    host_action?: string;
    run_name?: string;
    relative_path?: string;
  };
  const hostAction = (hostPayload.host_action || "—").trim();
  const meta = useMemo(
    () => job.payload_json?.execution_decision || {},
    [job.payload_json],
  );
  const tool = isHost
    ? "Host executor"
    : (meta as { tool_key?: string }).tool_key || (job.worker_type === DEV_AGENT ? "aider" : job.worker_type);
  const mode = (meta as { mode?: string }).mode || "—";
  const risk = job.risk_level || (meta as { risk_level?: string }).risk_level || "—";
  const badge = jobNeedsBadge(job.status);
  const needs = job.approval_required && job.status === "needs_approval";

  const riskIsHigh = String(risk).toLowerCase() === "high";

  async function decide(choice: "approve" | "deny") {
    setLoading(choice === "approve" ? "ap" : "den");
    try {
      const j = await webFetch<NexaJob>(`/web/jobs/${job.id}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision: choice === "approve" ? "approve" : "deny" }),
      });
      onUpdated?.(j);
      onNotify?.(choice === "approve" ? "Job approved" : "Job rejected");
    } catch (e) {
      onNotify?.((e as Error).message || "Could not update job");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div
      className="rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.06] to-transparent p-3 text-left shadow-[0_0_0_1px_rgba(255,255,255,0.04)]"
    >
      {!compact && (
        <div className="mb-2 space-y-1.5 text-[10px] uppercase tracking-wide text-zinc-500">
          {isHost ? (
            <div className="flex flex-wrap gap-x-4 gap-y-0.5">
              <span>
                Local action: <b className="text-zinc-200">{job.title}</b>
              </span>
              <span>
                Tool: <b className="text-zinc-200">{tool}</b>
              </span>
              <span>
                host_action: <b className="font-mono text-zinc-200">{hostAction}</b>
              </span>
              <span>
                Risk: <b className={riskTone(String(risk))}>{risk || "—"}</b>
              </span>
            </div>
          ) : (
            <div className="flex flex-wrap gap-x-4 gap-y-0.5">
              <span>
                Agent: <b className="text-zinc-200">Dev</b>
              </span>
              <span>
                Tool: <b className="text-zinc-200">{tool}</b>
              </span>
              <span>
                Mode: <b className="text-zinc-200">{mode}</b>
              </span>
              <span>
                Risk: <b className={riskTone(String(risk))}>{risk || "—"}</b>
              </span>
            </div>
          )}
        </div>
      )}

      <p className="line-clamp-2 text-sm font-medium text-zinc-100">
        {isHost ? `${job.title} · Job #${job.id}` : `Job #${job.id} · ${job.title}`}
      </p>
      {isHost && (
        <p className="mt-1.5 text-[10px] leading-relaxed text-zinc-400">
          Status: <span className="text-zinc-200">{job.status}</span>
          {job.approval_required ? " · Approval required before run" : ""}
        </p>
      )}
      {isHost && (
        <p className="mt-1.5 rounded border border-emerald-500/20 bg-emerald-500/5 px-2 py-1 text-[10px] text-emerald-100/90">
          Safety: This will run an allowlisted command only (no arbitrary shell). Paths stay under the configured work root.
        </p>
      )}
      {riskIsHigh && !isHost && (
        <p className="mt-1.5 rounded border border-amber-500/25 bg-amber-500/5 px-2 py-1 text-[10px] text-amber-200/90">
          This action may modify files. Review before approving.
        </p>
      )}
      {riskIsHigh && isHost && (
        <p className="mt-1.5 rounded border border-amber-500/25 bg-amber-500/5 px-2 py-1 text-[10px] text-amber-200/90">
          This action may read or write files under the work root. Review before approving.
        </p>
      )}
      {!compact && !isHost && (
        <details className="mt-2 text-[10px] text-zinc-500">
          <summary className="cursor-pointer text-zinc-500">Why Dev?</summary>
          <p className="mt-1 leading-relaxed text-zinc-500">
            This looks like a file or code change, so Nexa created a Dev Agent job.
            {job.approval_required
              ? " Approval is required because the job may modify files in your repo when it runs."
              : ""}
          </p>
        </details>
      )}
      {!compact && isHost && (
        <details className="mt-2 text-[10px] text-zinc-500">
          <summary className="cursor-pointer text-zinc-500">Why local?</summary>
          <p className="mt-1 leading-relaxed text-zinc-500">
            Chat never runs shell directly. Nexa queued a host-executor job; after you approve, the worker runs only
            allowlisted tools on your machine.
          </p>
        </details>
      )}
      {job.instruction && !compact && (
        <details
          className="mt-2 text-xs text-zinc-500"
          open={detailsOpen}
          onToggle={(e) => setDetailsOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary className="cursor-pointer text-zinc-400 hover:text-zinc-300">Execution & instruction</summary>
          <p className="mt-1 whitespace-pre-wrap break-words text-zinc-400">{job.instruction}</p>
        </details>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
            badge.tone === "emerald"
              ? "bg-emerald-500/20 text-emerald-200"
              : badge.tone === "amber"
                ? "bg-amber-500/15 text-amber-200/90"
                : badge.tone === "rose"
                  ? "bg-rose-500/15 text-rose-200"
                  : "bg-zinc-500/20 text-zinc-300"
          }`}
        >
          {["running", "queued", "in_progress"].includes(job.status) && (
            <span className="mr-1.5 h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
          )}
          {job.status}
        </span>
        {needs && (
          <>
            <button
              type="button"
              onClick={() => void decide("approve")}
              disabled={!!loading}
              className="rounded-lg bg-emerald-500/25 px-2.5 py-1 text-xs font-medium text-emerald-200 hover:bg-emerald-500/35 disabled:opacity-50"
            >
              {loading === "ap" ? "…" : "Approve"}
            </button>
            <button
              type="button"
              onClick={() => void decide("deny")}
              disabled={!!loading}
              className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-xs text-rose-200 hover:bg-rose-500/20 disabled:opacity-50"
            >
              {loading === "den" ? "…" : "Reject"}
            </button>
          </>
        )}
        {job.instruction && !compact && (
          <button
            type="button"
            onClick={() => setDetailsOpen((o) => !o)}
            className="text-[10px] text-zinc-500 underline decoration-zinc-600 hover:text-zinc-300"
          >
            View details
          </button>
        )}
      </div>
      {job.error_message && (
        <p className="mt-1 text-xs text-rose-300/90">{job.error_message}</p>
      )}
      {job.result && (
        <details className="mt-2 text-xs text-zinc-500">
          <summary className="cursor-pointer">Output (expand)</summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded-lg bg-black/30 p-2 text-zinc-400">{job.result}</pre>
        </details>
      )}
    </div>
  );
}
