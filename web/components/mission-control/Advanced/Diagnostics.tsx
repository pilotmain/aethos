"use client";

import { useCallback, useEffect, useState } from "react";

import type { DiagnosticInfo } from "@/types/mission-control";
import { type SystemHealthPayload, fetchSystemHealth, fetchSystemLogs, fetchSystemMetrics } from "@/lib/api/system";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, AlertCircle, CheckCircle, Clock, Database, RefreshCw, Server, XCircle } from "lucide-react";

interface DiagnosticsProps {
  onRefresh: () => Promise<DiagnosticInfo>;
}

export function Diagnostics({ onRefresh }: DiagnosticsProps) {
  const [diagnostics, setDiagnostics] = useState<DiagnosticInfo | null>(null);
  const [metricsPreview, setMetricsPreview] = useState<string>("");
  const [logsNote, setLogsNote] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadDiagnostics = useCallback(async () => {
    try {
      const data = await onRefresh();
      setDiagnostics(data);
      const [metrics, healthRaw, logs] = await Promise.all([
        fetchSystemMetrics().catch(() => ({})),
        fetchSystemHealth().catch(() => ({} as SystemHealthPayload)),
        fetchSystemLogs(),
      ]);
      const health = healthRaw as SystemHealthPayload;
      setMetricsPreview(
        JSON.stringify({ metrics, health: { providers: health.providers, offline_mode: health.offline_mode } }, null, 2),
      );
      setLogsNote(logs.note);
    } catch {
      setDiagnostics(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [onRefresh]);

  useEffect(() => {
    void loadDiagnostics();
  }, [loadDiagnostics]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadDiagnostics();
    } finally {
      setRefreshing(false);
    }
  };

  const getStatusIcon = (status: string) => {
    const s = status.toLowerCase();
    if (s === "healthy" || s === "running" || s === "ok") {
      return <CheckCircle className="h-4 w-4 text-emerald-400" />;
    }
    if (s === "degraded" || s === "warning") {
      return <AlertCircle className="h-4 w-4 text-amber-400" />;
    }
    return <XCircle className="h-4 w-4 text-red-400" />;
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  if (loading && !diagnostics) {
    return (
      <Card className="border-zinc-800 bg-zinc-900/40">
        <CardContent className="flex h-48 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
        </CardContent>
      </Card>
    );
  }

  if (!diagnostics) {
    return (
      <Card className="border-zinc-800 bg-zinc-900/40">
        <CardContent className="flex h-48 items-center justify-center">
          <p className="text-sm text-zinc-500">Failed to load diagnostics</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="border-zinc-800 bg-zinc-900/40">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-zinc-50">System diagnostics</CardTitle>
            <Button type="button" variant="outline" size="sm" className="border-zinc-700" onClick={() => void handleRefresh()} disabled={refreshing}>
              <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
          <CardDescription>GET /api/v1/system/health + /system/metrics (+ shallow /health).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <Server className="h-4 w-4" />
                API
              </div>
              <div className="flex items-center gap-2 text-zinc-200">
                {getStatusIcon(diagnostics.api_status)}
                <span className="capitalize">{diagnostics.api_status}</span>
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <Database className="h-4 w-4" />
                Database
              </div>
              <div className="flex items-center gap-2 text-zinc-200">
                {getStatusIcon(diagnostics.database_status)}
                <span>{diagnostics.database_status}</span>
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <Activity className="h-4 w-4" />
                Scheduler
              </div>
              <div className="flex items-center gap-2 text-zinc-200">
                {getStatusIcon(diagnostics.cron_status)}
                <span>{diagnostics.cron_status}</span>
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <Clock className="h-4 w-4" />
                Uptime
              </div>
              <span className="text-zinc-200">{formatUptime(diagnostics.uptime_seconds)}</span>
            </div>
          </div>

          <div className="space-y-2 border-t border-zinc-800 pt-4 text-sm text-zinc-400">
            <div className="flex justify-between gap-2">
              <span>Provider calls (process counter)</span>
              <span className="tabular-nums text-zinc-200">{diagnostics.workers}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span>Version</span>
              <span className="text-zinc-200">{diagnostics.version}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-zinc-800 bg-zinc-900/40">
        <CardHeader>
          <CardTitle className="text-base text-zinc-50">Logs</CardTitle>
          <CardDescription>{logsNote}</CardDescription>
        </CardHeader>
      </Card>

      <Card className="border-zinc-800 bg-zinc-900/40">
        <CardHeader>
          <CardTitle className="text-base text-zinc-50">Metrics snippet</CardTitle>
          <CardDescription>Safe counters from /system/metrics (no secrets).</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="max-h-56 overflow-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-300">
            {metricsPreview}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
