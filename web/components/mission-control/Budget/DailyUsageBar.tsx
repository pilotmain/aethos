"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type DailyUsageBarDatum = {
  date: string;
  label: string;
  tokens: number;
  cost: number;
};

interface DailyUsageBarProps {
  data: DailyUsageBarDatum[];
}

const tooltipStyle = {
  backgroundColor: "rgb(9 9 11)",
  border: "1px solid rgb(39 39 42)",
  borderRadius: "8px",
  color: "rgb(244 244 245)",
};

export function DailyUsageBar({ data }: DailyUsageBarProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-zinc-500">No daily buckets to chart yet</div>
    );
  }

  return (
    <div className="h-52 w-full min-h-[200px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
          <XAxis dataKey="label" stroke="#a1a1aa" tick={{ fontSize: 10 }} interval={0} angle={-12} textAnchor="end" height={48} />
          <YAxis stroke="#a1a1aa" tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v))} width={40} />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value, _name, item) => {
              const n = typeof value === "number" ? value : Number(value);
              const row = item && "payload" in item ? (item.payload as DailyUsageBarDatum | undefined) : undefined;
              const cost = row?.cost ?? 0;
              return [`${Number.isFinite(n) ? n.toLocaleString() : "0"} tokens · $${cost.toFixed(4)}`, "Day"];
            }}
          />
          <Bar dataKey="tokens" fill="#6366f1" name="tokens" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
