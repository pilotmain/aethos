"use client";

import { motion } from "framer-motion";

import {
  agentExecutionRing,
  executionBadge,
  executionHint,
  type ExecutionState,
} from "@/lib/mission-control/executionPresentation";

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
  /** Subtle emphasis on the current execution path (Phase 14). */
  pathHighlight?: boolean;
  /** P0 execution truth — only ``verified`` uses success/green styling. */
  execution_state?: ExecutionState | string | null;
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
  pathHighlight,
  execution_state,
  className = "",
}: AgentCardProps) {
  const st = (status || "unknown").toLowerCase();
  const ring = agentExecutionRing(status, execution_state);
  const pulse = st === "running";
  const badge = executionBadge(status, execution_state);
  const hint = executionHint(status, execution_state);
  const activeRing = active ? " ring-2 ring-violet-500/70 ring-offset-2 ring-offset-zinc-950" : "";
  const pathRing =
    pathHighlight && !active
      ? " shadow-[0_0_0_1px_rgba(139,92,246,0.35)] bg-violet-950/15"
      : "";

  return (
    <motion.div
      layout
      animate={{ scale: pulse ? 1.03 : 1 }}
      transition={{ type: "spring", stiffness: 380, damping: 26 }}
      className={`min-w-[160px] max-w-[260px] rounded-lg border bg-black/35 px-3 py-2.5 transition-[box-shadow,transform] duration-300 ${ring}${activeRing}${pathRing} ${className}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-zinc-100">{label}</div>
          {handle ? (
            <div className="truncate font-mono text-[11px] text-zinc-500">@{handle}</div>
          ) : null}
        </div>
        <span
          className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${badge.pillClass}`}
        >
          {badge.label}
        </span>
      </div>
      {hint ? <p className="mt-1 text-[10px] leading-snug text-amber-200/80">{hint}</p> : null}
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
