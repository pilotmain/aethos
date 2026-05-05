"use client";

import type { BudgetBand } from "@/types/mission-control";

export type BudgetGaugeProps = {
  percentage: number;
  status: BudgetBand;
};

export function BudgetGauge({ percentage, status }: BudgetGaugeProps) {
  const statusColor: Record<BudgetBand, string> = {
    active: "bg-emerald-500",
    warning: "bg-amber-500",
    paused: "bg-red-500",
  };

  const statusText: Record<BudgetBand, string> = {
    active: "Within budget",
    warning: "Approaching daily cap",
    paused: "Blocked or near exhaustion",
  };

  const pct = Math.min(100, Math.max(0, percentage));

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm text-zinc-300">
        <span>Daily token usage (est.)</span>
        <span className="tabular-nums">{Math.round(pct)}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-zinc-800">
        <div className={`h-2 rounded-full transition-all ${statusColor[status]}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex justify-between text-xs text-zinc-500">
        <span>{statusText[status]}</span>
        <span>{pct >= 99 ? "At or over cap" : `${Math.round(100 - pct)}% headroom`}</span>
      </div>
    </div>
  );
}
