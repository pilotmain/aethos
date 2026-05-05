"use client";

import { useEffect, useState } from "react";

import type { BudgetSettings } from "@/types/mission-control";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

interface BudgetSettingsProps {
  settings: BudgetSettings;
  onUpdate: (settings: Partial<BudgetSettings>) => Promise<void>;
}

export function BudgetSettingsComponent({ settings, onUpdate }: BudgetSettingsProps) {
  const [monthlyLimit, setMonthlyLimit] = useState(settings.monthly_limit.toString());
  const [warningThreshold, setWarningThreshold] = useState(settings.warning_threshold);
  const [alertsEnabled, setAlertsEnabled] = useState(settings.alerts_enabled);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMonthlyLimit(settings.monthly_limit.toString());
    setWarningThreshold(settings.warning_threshold);
    setAlertsEnabled(settings.alerts_enabled);
  }, [settings]);

  const handleSave = async () => {
    const n = parseInt(monthlyLimit, 10);
    if (!Number.isFinite(n) || n < 1000) {
      setError("Monthly target must be at least 1,000 tokens.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onUpdate({
        monthly_limit: n,
        warning_threshold: warningThreshold,
        alerts_enabled: alertsEnabled,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border-zinc-800 bg-zinc-900/40">
      <CardHeader>
        <CardTitle className="text-zinc-50">Budget settings</CardTitle>
        <CardDescription>
          Persists soft targets in <span className="text-zinc-400">ui_preferences</span> via POST /api/v1/user/settings. Daily
          enforcement still follows server env + token/cost checks.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <p className="text-sm text-red-400">{error}</p> : null}
        <div className="space-y-2">
          <Label htmlFor="monthly-limit" className="text-zinc-200">
            Monthly token target
          </Label>
          <Input
            id="monthly-limit"
            type="number"
            className="border-zinc-800 bg-zinc-950"
            value={monthlyLimit}
            onChange={(e) => setMonthlyLimit(e.target.value)}
          />
          <p className="text-xs text-zinc-500">
            Today: {settings.current_usage.toLocaleString()} tokens · Daily cap (UI gauge):{" "}
            {settings.daily_limit.toLocaleString()}
          </p>
        </div>

        <div className="space-y-2">
          <Label className="text-zinc-200">Warning threshold (% of daily cap)</Label>
          <div className="flex items-center gap-4">
            <Slider
              className="flex-1 py-2"
              value={[warningThreshold]}
              onValueChange={(value) => setWarningThreshold(value[0] ?? 80)}
              min={50}
              max={95}
              step={5}
            />
            <span className="w-12 text-sm tabular-nums text-zinc-300">{warningThreshold}%</span>
          </div>
          <p className="text-xs text-zinc-500">Critical alerts use {settings.critical_threshold}% (edit in DB or extend UI later).</p>
        </div>

        <div className="flex items-center justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2">
          <div className="space-y-0.5">
            <Label className="text-zinc-200">Budget alerts</Label>
            <p className="text-xs text-zinc-500">Mission Control derives alerts from usage + these thresholds.</p>
          </div>
          <Switch checked={alertsEnabled} onCheckedChange={setAlertsEnabled} />
        </div>

        <Button type="button" onClick={() => void handleSave()} disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </Button>
      </CardContent>
    </Card>
  );
}
