"use client";

import { MemberCard } from "@/components/mission-control/Team/MemberCard";
import type { TeamMember } from "@/types/mission-control";

export type MemberListProps = {
  title: string;
  description?: string;
  members: TeamMember[];
  currentUserId: string;
  onRoleChange?: (userId: string, newRole: string) => void;
  onRemove?: (userId: string) => void;
};

export function MemberList({
  title,
  description,
  members,
  currentUserId,
  onRoleChange,
  onRemove,
}: MemberListProps) {
  if (!members.length) return null;

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">{title}</h3>
        {description ? <p className="text-xs text-zinc-600">{description}</p> : null}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {members.map((m) => (
          <MemberCard
            key={m.id}
            member={m}
            isCurrentUser={m.kind === "human" && m.user_id === currentUserId}
            onRoleChange={m.kind === "human" ? onRoleChange : undefined}
            onRemove={m.kind === "human" ? onRemove : undefined}
          />
        ))}
      </div>
    </div>
  );
}
