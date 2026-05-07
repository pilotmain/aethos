"use client";

import { MoreVertical, Trash2, UserCog } from "lucide-react";

import { AssignTaskDialog } from "@/components/mission-control/Team/AssignTaskDialog";
import { RoleBadge } from "@/components/mission-control/Team/RoleBadge";
import { StatusIndicator } from "@/components/mission-control/Team/StatusIndicator";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { TeamMember } from "@/types/mission-control";

const GOV_ROLE_OPTIONS = ["admin", "member", "viewer", "auditor"] as const;

export type MemberCardProps = {
  member: TeamMember;
  onRoleChange?: (userId: string, newRole: string) => void;
  onRemove?: (userId: string) => void;
  /** Called after a successful agent assignment so the parent can refresh. */
  onAssigned?: () => void | Promise<void>;
  isCurrentUser?: boolean;
};

export function MemberCard({ member, onRoleChange, onRemove, onAssigned, isCurrentUser }: MemberCardProps) {
  const initial = (member.name || member.user_id || "?").charAt(0).toUpperCase();
  const showMenu = member.kind === "human" && !isCurrentUser && (onRoleChange || onRemove);

  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-950/40 p-4">
      <div className="flex min-w-0 flex-1 items-center gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-violet-600/20 text-sm font-semibold text-violet-100">
          {initial}
        </div>
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-zinc-100">{member.name}</span>
            {member.kind === "agent" ? (
              <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
                Agent
              </span>
            ) : null}
            {isCurrentUser ? <span className="text-xs text-zinc-500">(you)</span> : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusIndicator status={member.status} showLabel size="sm" />
            <RoleBadge roleKey={member.roleKey} label={member.roleLabel} size="sm" />
          </div>
          {member.current_task ? (
            <p className="text-xs text-zinc-500">Working on: {member.current_task}</p>
          ) : null}
          <p className="font-mono text-[11px] text-zinc-600 truncate">{member.user_id}</p>
        </div>
      </div>

      {member.kind === "agent" && member.user_id ? (
        <AssignTaskDialog
          agentHandle={member.user_id}
          agentDisplayName={member.name}
          agentDomain={member.roleLabel}
          disabled={member.status === "busy"}
          disabledReason={member.status === "busy" ? "Agent is busy — try again when idle." : undefined}
          onAssigned={onAssigned}
        />
      ) : null}

      {showMenu ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="shrink-0 text-zinc-400" aria-label="Member actions">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            {onRoleChange
              ? GOV_ROLE_OPTIONS.map((role) => (
                  <DropdownMenuItem
                    key={role}
                    onClick={() => onRoleChange(member.user_id, role)}
                    disabled={member.roleLabel.toLowerCase() === role}
                  >
                    <UserCog className="mr-2 h-4 w-4" />
                    Set role: {role}
                  </DropdownMenuItem>
                ))
              : null}
            {onRemove ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-red-400 focus:text-red-300"
                  onClick={() => onRemove(member.user_id)}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Disable member
                </DropdownMenuItem>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
    </div>
  );
}
