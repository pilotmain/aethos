"use client";

import type { AttentionActivityItem } from "@/types/mission-control";

export type ActivityFeedProps = {
  items: AttentionActivityItem[];
};

export function ActivityFeed({ items }: ActivityFeedProps) {
  if (!items.length) {
    return (
      <p className="text-sm text-zinc-500">
        No attention items — orchestration queue is quiet for this window.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {items.map((it) => (
        <li key={it.id} className="rounded-lg border border-zinc-800 bg-zinc-950/30 px-3 py-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide">
              {it.type}
            </span>
            {it.created_at ? <span>{new Date(it.created_at).toLocaleString()}</span> : null}
          </div>
          <p className="mt-1 text-sm font-medium text-zinc-100">{it.title}</p>
          {it.description ? <p className="mt-1 text-xs text-zinc-500 line-clamp-3">{it.description}</p> : null}
        </li>
      ))}
    </ul>
  );
}
