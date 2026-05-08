"use client";

import type { JSX } from "react";

/** Unified diff lines — same styling as Mission Control self-improvement (Phase 73b). */
export function DiffViewer({ unified }: { unified: string }): JSX.Element {
  const lines = unified.split("\n");
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950/80 p-3">
      <div className="max-h-96 overflow-auto">
        {lines.map((line, i) => {
          let cls = "text-zinc-300";
          if (
            line.startsWith("+++") ||
            line.startsWith("---") ||
            line.startsWith("diff --git")
          ) {
            cls = "text-zinc-400";
          } else if (line.startsWith("@@")) {
            cls = "text-cyan-300";
          } else if (line.startsWith("+")) {
            cls = "text-emerald-300";
          } else if (line.startsWith("-")) {
            cls = "text-rose-300";
          }
          return (
            <div key={i} className={`whitespace-pre font-mono text-xs ${cls}`}>
              {line || "\u00A0"}
            </div>
          );
        })}
      </div>
    </div>
  );
}
