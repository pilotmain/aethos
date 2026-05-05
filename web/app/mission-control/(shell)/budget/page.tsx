"use client";

import { useCallback, useEffect, useState } from "react";

import { BudgetAlerts } from "@/components/mission-control/Budget/BudgetAlerts";
import { BudgetSettingsComponent } from "@/components/mission-control/Budget/BudgetSettings";
import { DailyUsageBar } from "@/components/mission-control/Budget/DailyUsageBar";
import { ForecastCard } from "@/components/mission-control/Budget/ForecastCard";
import { MemberUsageTable } from "@/components/mission-control/Budget/MemberUsageTable";
import { ProviderBreakdown } from "@/components/mission-control/Budget/ProviderBreakdown";
import { UsageChart } from "@/components/mission-control/Budget/UsageChart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatMissionControlApiError } from "@/lib/api";
import {
  acknowledgeBudgetAlert,
  loadBudgetDashboardData,
  updateBudgetSettings,
} from "@/lib/api/budget";
import type { BudgetDashboardData } from "@/lib/api/budget";
import type { BudgetSettings } from "@/types/mission-control";

export default function MissionControlBudgetPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<BudgetDashboardData | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await loadBudgetDashboardData();
      setData(d);
      if (d.loadError) {
        setError(formatMissionControlApiError(d.loadError));
      }
    } catch (e) {
      setData(null);
      setError(formatMissionControlApiError(e instanceof Error ? e.message : String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleAcknowledgeAlert = (alertId: string) => {
    acknowledgeBudgetAlert(alertId);
    void load();
  };

  const handleUpdateSettings = async (updates: Partial<BudgetSettings>) => {
    await updateBudgetSettings(updates);
    await load();
  };

  if (loading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
          <p className="mt-2 text-sm text-zinc-500">Loading budget data…</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-zinc-50">Budget &amp; usage</h1>
        {error ? (
          <div className="rounded-lg border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-200">{error}</div>
        ) : (
          <p className="text-zinc-400">No data.</p>
        )}
      </div>
    );
  }

  const totalTokens = data.memberUsage.reduce((sum, m) => sum + m.tokens, 0);
  const hasUnackedAlerts = data.alerts.some((a) => !a.acknowledged);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-50">Budget &amp; usage</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Data from GET /api/v1/providers/usage (audit tail + today&apos;s roll-up) and POST /api/v1/user/settings for soft
          targets. There is no separate /budget/* router yet.
        </p>
      </div>

      {error ? (
        <div className="rounded-lg border border-amber-900/40 bg-amber-950/30 px-4 py-3 text-sm text-amber-100">{error}</div>
      ) : null}

      {hasUnackedAlerts ? (
        <Card className="border-zinc-800 bg-zinc-900/40">
          <CardHeader>
            <CardTitle className="text-zinc-50">Active alerts</CardTitle>
            <CardDescription>Thresholds use your saved warning % and live daily cap usage.</CardDescription>
          </CardHeader>
          <CardContent>
            <BudgetAlerts alerts={data.alerts} onAcknowledge={handleAcknowledgeAlert} />
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card className="border-zinc-800 bg-zinc-900/40">
            <CardHeader>
              <CardTitle className="text-zinc-50">Usage over time</CardTitle>
              <CardDescription>Daily buckets from recent provider audits (timestamps synthesized when only tail entries exist).</CardDescription>
            </CardHeader>
            <CardContent>
              <UsageChart data={data.usageHistory} />
            </CardContent>
          </Card>
          <Card className="border-zinc-800 bg-zinc-900/40">
            <CardHeader>
              <CardTitle className="text-zinc-50">Last seven days</CardTitle>
              <CardDescription>Token totals per day (cost in tooltip).</CardDescription>
            </CardHeader>
            <CardContent>
              <DailyUsageBar data={data.dailyBars} />
            </CardContent>
          </Card>
        </div>
        <div>
          <ForecastCard
            forecast={data.forecast}
            currentUsage={data.settings.current_usage}
            monthlyLimit={data.settings.monthly_limit}
          />
        </div>
      </div>

      <Tabs defaultValue="providers" className="space-y-4">
        <TabsList>
          <TabsTrigger value="providers">By provider</TabsTrigger>
          <TabsTrigger value="members">By source</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="providers">
          <Card className="border-zinc-800 bg-zinc-900/40">
            <CardHeader>
              <CardTitle className="text-zinc-50">Provider breakdown</CardTitle>
              <CardDescription>Token distribution from recent audit entries.</CardDescription>
            </CardHeader>
            <CardContent>
              <ProviderBreakdown providers={data.providerBreakdown} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="members">
          <Card className="border-zinc-800 bg-zinc-900/40">
            <CardHeader>
              <CardTitle className="text-zinc-50">Usage table</CardTitle>
              <CardDescription>Sorted columns; share bars are % of tokens in this breakdown.</CardDescription>
            </CardHeader>
            <CardContent>
              <MemberUsageTable members={data.memberUsage} totalTokens={totalTokens} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings">
          <BudgetSettingsComponent settings={data.settings} onUpdate={handleUpdateSettings} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
