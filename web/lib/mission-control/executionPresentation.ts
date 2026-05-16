/**
 * Mission Control execution truth — loop completion ≠ verified real-world execution (P0).
 * Only `verified` uses success/green styling.
 */

export type ExecutionState =
  | "verified"
  | "diagnostic_only"
  | "access_required"
  | "not_executed"
  | "completed_unverified"
  | "unknown";

const BASE_RING: Record<string, string> = {
  queued: "border-zinc-600",
  pending: "border-zinc-600",
  running: "border-orange-500/80 shadow-[0_0_12px_rgba(249,115,22,0.25)]",
  failed: "border-red-500/70",
  blocked: "border-amber-500/60",
  cancelled: "border-zinc-700",
};

/** Border classes for the agent card — completed uses execution truth, not generic green. */
export function agentExecutionRing(status: string, executionState?: ExecutionState | string | null): string {
  const st = (status || "unknown").toLowerCase();
  if (st === "completed") {
    const es = executionState as ExecutionState | undefined;
    if (es === "verified") return "border-emerald-600/60";
    if (es === "diagnostic_only" || es === "completed_unverified") return "border-amber-500/70";
    if (es === "access_required") return "border-zinc-500/70";
    return "border-amber-500/60";
  }
  return BASE_RING[st] ?? "border-zinc-700";
}

export type ExecutionBadge = {
  label: string;
  /** Tailwind text/bg classes for the pill */
  pillClass: string;
};

export function executionBadge(status: string, executionState?: ExecutionState | string | null): ExecutionBadge {
  const st = (status || "unknown").toLowerCase();
  const es = executionState as ExecutionState | undefined;
  const muted = "bg-zinc-900/90 text-zinc-400";

  if (st === "running") {
    return { label: "running", pillClass: "bg-orange-950/80 text-orange-200/95" };
  }

  if (st === "completed") {
    if (es === "verified") {
      return { label: "Verified", pillClass: "bg-emerald-950/90 text-emerald-200/95" };
    }
    if (es === "diagnostic_only") {
      return { label: "Diagnostic only", pillClass: "bg-amber-950/85 text-amber-200/95" };
    }
    if (es === "access_required") {
      return { label: "Access required", pillClass: muted };
    }
    if (es === "completed_unverified") {
      return { label: "Completed unverified", pillClass: "bg-amber-950/85 text-amber-200/95" };
    }
    return { label: "Not verified", pillClass: muted };
  }

  return { label: st, pillClass: muted };
}

/** Helper line under the card header — empty when nothing extra to say */
export function executionHint(status: string, executionState?: ExecutionState | string | null): string | null {
  const st = (status || "unknown").toLowerCase();
  const es = executionState as ExecutionState | undefined;
  if (st !== "completed") return null;
  if (es === "diagnostic_only") {
    return "Diagnostic only — no deploy, push, or external repair was verified.";
  }
  if (es === "access_required") {
    return "Access required — connect credentials before AethOS can inspect or act.";
  }
  if (es === "completed_unverified") {
    return "Workflow ended, but no real-world execution was verified.";
  }
  return null;
}
