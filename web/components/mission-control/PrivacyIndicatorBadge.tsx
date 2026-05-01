"use client";

import type { PrivacyIndicator } from "@/lib/mission-control/useMissionControlSnapshot";

const STYLE: Record<string, string> = {
  safe: "border-emerald-500/40 bg-emerald-950/40 text-emerald-100",
  redacted: "border-amber-500/45 bg-amber-950/45 text-amber-100",
  blocked: "border-rose-500/45 bg-rose-950/45 text-rose-100",
};

const DOT: Record<string, string> = {
  safe: "bg-emerald-400",
  redacted: "bg-amber-400",
  blocked: "bg-rose-500",
};

export function PrivacyIndicatorBadge({
  indicator,
  compact,
}: {
  indicator: PrivacyIndicator | null | undefined;
  compact?: boolean;
}) {
  const level = indicator?.level ?? "safe";
  const label = indicator?.label ?? "Privacy";
  const cls = STYLE[level] ?? STYLE.safe;
  const dot = DOT[level] ?? DOT.safe;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium ${cls}`}
      title="Derived from recent privacy firewall events (PII-first platform)."
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${dot}`} aria-hidden />
      {!compact ? <span className="text-zinc-400">PII layer ·</span> : null}
      <span>{label}</span>
    </span>
  );
}
