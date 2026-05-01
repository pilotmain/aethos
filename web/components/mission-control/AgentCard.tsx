"use client";

import { motion } from "framer-motion";

const STATUS_RING: Record<string, string> = {
  queued: "border-zinc-600",
  pending: "border-zinc-600",
  running: "border-orange-500/80 shadow-[0_0_12px_rgba(249,115,22,0.25)]",
  completed: "border-emerald-600/60",
  failed: "border-red-500/70",
  blocked: "border-amber-500/60",
  cancelled: "border-zinc-700",
};

function truncate(s: string, max: number): string {
  const t = s.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

export type AgentCardProps = {
  label: string;
  handle?: string;
  status: string;
  /** Last structured task output or artifact snippet */
  lastOutput?: string | null;
  nodeId?: string;
  /** Highlight when this agent is the active runner (Phase 13). */
  active?: boolean;
  className?: string;
};

/**
 * Mission Control v2 — agent tile with status accent and subtle motion while running.
 */
export function AgentCard({
  label,
  handle,
  status,
  lastOutput,
  nodeId,
  active,
  className = "",
}: AgentCardProps) {
  const st = (status || "unknown").toLowerCase();
  const ring = STATUS_RING[st] ?? "border-zinc-700";
  const pulse = st === "running";
  const activeRing = active ? " ring-2 ring-violet-500/70 ring-offset-2 ring-offset-zinc-950" : "";

  return (
    <motion.div
      layout
      animate={{ scale: pulse ? 1.03 : 1 }}
      transition={{ type: "spring", stiffness: 380, damping: 26 }}
      className={`min-w-[160px] max-w-[260px] rounded-lg border bg-black/35 px-3 py-2.5 transition-[box-shadow,transform] duration-300 ${ring}${activeRing} ${className}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-zinc-100">{label}</div>
          {handle ? (
            <div className="truncate font-mono text-[11px] text-zinc-500">@{handle}</div>
          ) : null}
        </div>
        <span className="shrink-0 rounded bg-zinc-900/90 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
          {st}
        </span>
      </div>
      {nodeId ? <div className="mt-1 truncate font-mono text-[10px] text-zinc-600">{nodeId}</div> : null}
      <div className="mt-2 border-t border-zinc-800/80 pt-2 text-[11px] leading-snug text-zinc-400">
        <span className="text-zinc-600">Last output — </span>
        {lastOutput ? (
          <span className="text-zinc-300">{truncate(lastOutput, 280)}</span>
        ) : (
          <span className="italic text-zinc-600">No output yet</span>
        )}
      </div>
    </motion.div>
  );
}
