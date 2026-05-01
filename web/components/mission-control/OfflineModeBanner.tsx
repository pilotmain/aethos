"use client";

import { WifiOff } from "lucide-react";

export function OfflineModeBanner({
  offline,
  strictMode,
}: {
  offline?: boolean;
  strictMode?: boolean;
}) {
  if (strictMode) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-violet-500/35 bg-violet-950/35 px-3 py-2 text-xs text-violet-100">
        <span className="font-semibold">Strict privacy mode</span>
        <span className="text-violet-200/90">
          External LLM providers are blocked — only local_stub / on-device tools run.
        </span>
      </div>
    );
  }
  if (!offline) return null;
  return (
    <div className="flex items-center gap-2 rounded-lg border border-sky-500/35 bg-sky-950/35 px-3 py-2 text-xs text-sky-100">
      <WifiOff className="h-4 w-4 shrink-0" aria-hidden />
      <span>
        <span className="font-semibold">Running in local mode</span>
        <span className="text-sky-200/90"> — No OpenAI/Anthropic keys detected; missions use local routing.</span>
      </span>
    </div>
  );
}
