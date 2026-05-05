"use client";

import type { TeamMemberStatus } from "@/types/mission-control";
import { cn } from "@/lib/utils";

export type StatusIndicatorProps = {
  status: TeamMemberStatus;
  showLabel?: boolean;
  size?: "sm" | "md" | "lg";
};

const statusConfig: Record<
  TeamMemberStatus,
  { color: string; label: string; pulse?: boolean }
> = {
  active: { color: "bg-emerald-500", label: "Active", pulse: true },
  busy: { color: "bg-rose-500", label: "Busy", pulse: true },
  idle: { color: "bg-amber-400", label: "Idle", pulse: false },
  offline: { color: "bg-zinc-600", label: "Offline", pulse: false },
};

export function StatusIndicator({ status, showLabel = false, size = "md" }: StatusIndicatorProps) {
  const config = statusConfig[status];
  const sizeClasses = {
    sm: "h-2 w-2",
    md: "h-3 w-3",
    lg: "h-4 w-4",
  };

  return (
    <div className="flex items-center gap-1.5">
      <div
        className={cn(sizeClasses[size], "rounded-full", config.color, config.pulse && "animate-pulse")}
        aria-hidden
      />
      {showLabel ? <span className="text-xs text-zinc-500">{config.label}</span> : null}
    </div>
  );
}
