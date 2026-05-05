"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { UsageRecord } from "@/types/mission-control";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface UsageChartProps {
  data: UsageRecord[];
  title?: string;
}

const tooltipStyle = {
  backgroundColor: "rgb(9 9 11)",
  border: "1px solid rgb(39 39 42)",
  borderRadius: "8px",
  color: "rgb(244 244 245)",
};

export function UsageChart({ data, title }: UsageChartProps) {
  const formatDate = (date: string) => {
    try {
      return new Date(date).toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch {
      return date;
    }
  };

  const formatTokens = (value: number) => {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(0)}K`;
    return String(Math.round(value));
  };

  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-zinc-500">No usage data available</div>
    );
  }

  return (
    <div className="space-y-4">
      {title ? <h3 className="text-lg font-semibold text-zinc-50">{title}</h3> : null}
      <Tabs defaultValue="tokens" className="w-full">
        <TabsList>
          <TabsTrigger value="tokens">Tokens</TabsTrigger>
          <TabsTrigger value="cost">Cost (USD)</TabsTrigger>
        </TabsList>
        <TabsContent value="tokens">
          <div className="h-80 w-full min-h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                <XAxis dataKey="date" stroke="#a1a1aa" tickFormatter={formatDate} tick={{ fontSize: 11 }} />
                <YAxis stroke="#a1a1aa" tickFormatter={formatTokens} tick={{ fontSize: 11 }} width={48} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelFormatter={(label) => formatDate(String(label))}
                  formatter={(value) => {
                    const n = typeof value === "number" ? value : Number(value);
                    return [`${Number.isFinite(n) ? n.toLocaleString() : "0"} tokens`, "Usage"];
                  }}
                />
                <Legend wrapperStyle={{ color: "#d4d4d8" }} />
                <Area
                  type="monotone"
                  dataKey="tokens"
                  stroke="#818cf8"
                  fill="#6366f1"
                  fillOpacity={0.15}
                  name="Tokens"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </TabsContent>
        <TabsContent value="cost">
          <div className="h-80 w-full min-h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                <XAxis dataKey="date" stroke="#a1a1aa" tickFormatter={formatDate} tick={{ fontSize: 11 }} />
                <YAxis stroke="#a1a1aa" tickFormatter={(value) => `$${Number(value).toFixed(4)}`} tick={{ fontSize: 11 }} width={56} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelFormatter={(label) => formatDate(String(label))}
                  formatter={(value) => {
                    const n = typeof value === "number" ? value : Number(value);
                    return [`$${Number.isFinite(n) ? n.toFixed(6) : "0.000000"}`, "Cost"];
                  }}
                />
                <Legend wrapperStyle={{ color: "#d4d4d8" }} />
                <Line type="monotone" dataKey="cost" stroke="#f87171" strokeWidth={2} dot={false} name="Cost (USD)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
