"use client";

import { Bot, Crown, Eye, Shield, User } from "lucide-react";

import type { GovernanceRoleKey } from "@/types/mission-control";
import { cn } from "@/lib/utils";

export type RoleBadgeProps = {
  roleKey: GovernanceRoleKey | "agent_role";
  /** Raw label from API (always shown). */
  label: string;
  size?: "sm" | "md";
};

const govTone: Record<GovernanceRoleKey, { Icon: typeof Crown; className: string }> = {
  owner: {
    Icon: Crown,
    className: "border border-amber-800/60 bg-amber-950/40 text-amber-200",
  },
  admin: {
    Icon: Shield,
    className: "border border-sky-800/60 bg-sky-950/40 text-sky-200",
  },
  member: {
    Icon: User,
    className: "border border-zinc-700 bg-zinc-800/80 text-zinc-200",
  },
  viewer: {
    Icon: Eye,
    className: "border border-zinc-700 bg-zinc-900 text-zinc-400",
  },
  auditor: {
    Icon: Eye,
    className: "border border-violet-800/60 bg-violet-950/40 text-violet-200",
  },
};

export function RoleBadge({ roleKey, label, size = "md" }: RoleBadgeProps) {
  if (roleKey === "agent_role") {
    const pad = size === "sm" ? "gap-1 px-2 py-0.5 text-xs" : "gap-1.5 px-2.5 py-1 text-sm";
    return (
      <div
        className={cn(
          "inline-flex max-w-full items-center rounded-full font-medium border border-violet-800/50 bg-violet-950/30 text-violet-200",
          pad,
        )}
      >
        <Bot className={size === "sm" ? "h-3 w-3 shrink-0" : "h-3.5 w-3.5 shrink-0"} aria-hidden />
        <span className="truncate">{label}</span>
      </div>
    );
  }

  const { Icon, className } = govTone[roleKey];
  const pad = size === "sm" ? "gap-1 px-2 py-0.5 text-xs" : "gap-1.5 px-2.5 py-1 text-sm";

  return (
    <div className={cn("inline-flex max-w-full items-center rounded-full font-medium", pad, className)}>
      <Icon className={size === "sm" ? "h-3 w-3 shrink-0" : "h-3.5 w-3.5 shrink-0"} aria-hidden />
      <span className="truncate capitalize">{label}</span>
    </div>
  );
}
