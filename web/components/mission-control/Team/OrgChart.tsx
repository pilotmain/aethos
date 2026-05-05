"use client";

import { RoleBadge } from "@/components/mission-control/Team/RoleBadge";
import type { OrgChartNode } from "@/types/mission-control";
import { cn } from "@/lib/utils";

export type OrgChartProps = {
  nodes: OrgChartNode[];
};

function TreeNode({ node, level = 0 }: { node: OrgChartNode; level: number }) {
  const hasChildren = node.children && node.children.length > 0;
  const initial = (node.name || "?").charAt(0).toUpperCase();

  return (
    <div className="relative">
      <div
        className={cn(
          "relative flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3",
          level > 0 && "ml-6 border-l border-l-zinc-800 pl-4",
        )}
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-violet-600/20 text-sm font-semibold text-violet-100">
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-zinc-100">{node.name}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <RoleBadge roleKey="agent_role" label={node.role} size="sm" />
          </div>
        </div>
      </div>

      {hasChildren ? (
        <div className="ml-4 mt-2 space-y-2 border-l border-zinc-800/80 pl-3">
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} level={level + 1} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function OrgChart({ nodes }: OrgChartProps) {
  if (!nodes?.length) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-zinc-800 text-sm text-zinc-500">
        No agent hierarchy yet — configure Agent Organization roles and reporting lines.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {nodes.map((node) => (
        <TreeNode key={node.id} node={node} level={0} />
      ))}
    </div>
  );
}
