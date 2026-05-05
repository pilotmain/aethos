"use client";

import type { UsageForecast } from "@/types/mission-control";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertTriangle, TrendingUp } from "lucide-react";

interface ForecastCardProps {
  forecast: UsageForecast;
  currentUsage: number;
  monthlyLimit: number;
}

export function ForecastCard({ forecast, currentUsage, monthlyLimit }: ForecastCardProps) {
  const willExceed = forecast.projected_total > monthlyLimit;
  const excess = forecast.projected_total - monthlyLimit;
  const daysLeft = forecast.days_remaining;

  return (
    <Card className="border-zinc-800 bg-zinc-900/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-zinc-50">
          <TrendingUp className="h-4 w-4 text-violet-400" />
          Usage forecast
        </CardTitle>
        <CardDescription>Heuristic from recent audit density + today&apos;s roll-up (not a stored forecast API).</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-zinc-500">Current (today)</p>
            <p className="text-2xl font-bold tabular-nums text-zinc-50">{currentUsage.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-sm text-zinc-500">Projected month-end</p>
            <p className={`text-2xl font-bold tabular-nums ${willExceed ? "text-red-400" : "text-emerald-400"}`}>
              {forecast.projected_total.toLocaleString()}
            </p>
            <p className="text-xs text-zinc-500">Est. cost ${forecast.projected_cost.toFixed(4)}</p>
          </div>
        </div>

        {willExceed ? (
          <div className="rounded-lg border border-red-900/50 bg-red-950/30 p-3">
            <div className="flex items-center gap-2 text-red-300">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span className="text-sm font-medium">
                Projected to exceed monthly target by {excess.toLocaleString()} tokens
              </span>
            </div>
            <p className="mt-1 text-xs text-red-200/80">
              Tune the monthly target in settings or reduce usage; server enforcement still uses daily caps from env + user
              cost limits.
            </p>
          </div>
        ) : null}

        <div className="space-y-2 border-t border-zinc-800 pt-4 text-sm text-zinc-400">
          <div className="flex justify-between gap-2">
            <span>Daily average (from chart buckets)</span>
            <span className="tabular-nums text-zinc-200">{forecast.estimated_daily_average.toLocaleString()} tokens/day</span>
          </div>
          <div className="flex justify-between gap-2">
            <span>Days remaining (this month)</span>
            <span className="tabular-nums text-zinc-200">{daysLeft}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span>Recommended daily cap (to target)</span>
            <span className="tabular-nums text-zinc-200">{forecast.recommended_daily_cap.toLocaleString()} tokens/day</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
