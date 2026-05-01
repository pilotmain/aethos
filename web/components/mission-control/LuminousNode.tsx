"use client";

export type LuminousStatus =
  | "queued"
  | "running"
  | "waiting_approval"
  | "waiting_worker"
  | "completed"
  | "failed"
  | "blocked";

export type LuminousNodeProps = {
  handle: string;
  status: LuminousStatus;
  pulseRateSec?: number;
  label?: string;
};

function borderClass(status: LuminousStatus): string {
  switch (status) {
    case "failed":
      return "border-red-500/90";
    case "completed":
      return "border-emerald-500/85";
    case "blocked":
      return "border-amber-500/85";
    default:
      return "border-cyan-400/70";
  }
}

/** Live assignment node — server-backed status only (no LLM text). */
export function LuminousNode({ handle, status, label }: LuminousNodeProps) {
  const active = status === "running" || status === "waiting_approval" || status === "waiting_worker";

  return (
    <div
      className={`relative rounded-2xl border bg-zinc-950/50 p-4 shadow-lg backdrop-blur-sm ${borderClass(
        status,
      )} ${active ? "shadow-[0_0_22px_rgba(34,211,238,0.38)]" : ""}`}
    >
      {active ? (
        <span
          className="pointer-events-none absolute inset-0 rounded-2xl bg-cyan-400/10 animate-pulse"
          aria-hidden
        />
      ) : null}
      <div className="relative">
        <div className="text-[11px] uppercase tracking-wide text-zinc-500">{status.replace(/_/g, " ")}</div>
        <div className="text-lg font-semibold text-zinc-100">@{handle.replace(/^@/, "")}</div>
        {label ? <div className="mt-1 line-clamp-2 text-xs text-zinc-400">{label}</div> : null}
      </div>
    </div>
  );
}
