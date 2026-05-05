"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { ProviderUsage } from "@/types/mission-control";

interface ProviderBreakdownProps {
  providers: ProviderUsage[];
}

const COLORS = ["#6366f1", "#f87171", "#34d399", "#fbbf24", "#a78bfa", "#f472b6"];

const tooltipStyle = {
  backgroundColor: "rgb(9 9 11)",
  border: "1px solid rgb(39 39 42)",
  borderRadius: "8px",
  color: "rgb(244 244 245)",
};

export function ProviderBreakdown({ providers }: ProviderBreakdownProps) {
  const chartData = (providers || []).map((p) => ({
    ...p,
    name: p.name || p.provider,
  }));

  if (!chartData.length) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-zinc-500">No provider data available</div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="h-64 w-full min-h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={52}
              outerRadius={76}
              paddingAngle={2}
              dataKey="tokens"
              nameKey="name"
              labelLine={false}
              label={({ name, percent }) => `${String(name)}: ${((percent ?? 0) * 100).toFixed(0)}%`}
            >
              {chartData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(value, _name, item) => {
                const n = typeof value === "number" ? value : Number(value);
                const row = item && "payload" in item ? (item.payload as ProviderUsage | undefined) : undefined;
                const cost = row?.cost ?? 0;
                const tok = Number.isFinite(n) ? n : 0;
                return [`${tok.toLocaleString()} tokens ($${cost.toFixed(4)})`, "Usage"];
              }}
            />
            <Legend wrapperStyle={{ color: "#d4d4d8" }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="grid gap-2">
        {chartData.map((provider, index) => (
          <div key={provider.provider} className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
              <span className="text-zinc-200">{provider.provider}</span>
            </div>
            <div className="flex flex-wrap gap-4 text-zinc-400">
              <span className="tabular-nums text-zinc-200">{provider.tokens.toLocaleString()} tokens</span>
              <span className="tabular-nums">${provider.cost.toFixed(4)}</span>
              <span className="tabular-nums">{provider.percentage.toFixed(1)}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
