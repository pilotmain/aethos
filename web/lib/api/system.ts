import type { DiagnosticInfo } from "@/types/mission-control";

import { apiFetch } from "@/lib/api/client";
import { fetchHealth } from "@/lib/api/health";

export type SystemHealthPayload = {
  ok?: boolean;
  status?: string;
  db?: string;
  scheduler?: string;
  privacy_mode?: string;
  runtime?: string;
  providers?: string;
  uptime_seconds?: number;
  version?: string;
  offline_mode?: boolean;
  strict_privacy?: boolean;
  provider_tags?: string[];
};

export type SystemMetricsPayload = {
  http_requests_total?: number;
  provider_calls_total?: number;
  provider_latency_avg_ms?: number;
  uptime_seconds?: number;
};

export type WebIndicatorItem = {
  id: string;
  label: string;
  level: string;
  detail?: string | null;
};

export type WebSystemStatusPayload = {
  indicators?: WebIndicatorItem[];
};

export async function fetchSystemHealth(): Promise<SystemHealthPayload> {
  return apiFetch<SystemHealthPayload>("/system/health");
}

export async function fetchSystemMetrics(): Promise<SystemMetricsPayload> {
  return apiFetch<SystemMetricsPayload>("/system/metrics");
}

export async function fetchWebSystemStatus(): Promise<WebSystemStatusPayload> {
  return apiFetch<WebSystemStatusPayload>("/web/system/status");
}

/** `/system/logs` is not implemented — kept for future wiring. */
export async function fetchSystemLogs(): Promise<{ lines: string[]; note: string }> {
  return {
    lines: [],
    note: "GET /api/v1/system/logs is not available in this Nexa build. Use host/container logs or your process manager.",
  };
}

export function mapSystemPayloadsToDiagnostics(
  health: SystemHealthPayload,
  metrics: SystemMetricsPayload,
): DiagnosticInfo {
  const apiOk = Boolean(health.ok);
  const st = String(health.status || "").toLowerCase();
  const api_status: DiagnosticInfo["api_status"] = apiOk ? "healthy" : st === "degraded" ? "degraded" : "down";
  const db = String(health.db || "").toLowerCase();
  const database_status: DiagnosticInfo["database_status"] = db === "connected" ? "healthy" : "error";
  const sched = String(health.scheduler || "").toLowerCase();
  const cron_status: DiagnosticInfo["cron_status"] = sched === "running" ? "running" : "stopped";
  const workers = Number(metrics.provider_calls_total ?? metrics.http_requests_total ?? 0);
  const up = Number(health.uptime_seconds ?? metrics.uptime_seconds ?? 0);
  return {
    api_status,
    database_status,
    cron_status,
    workers: Number.isFinite(workers) ? workers : 0,
    uptime_seconds: Number.isFinite(up) ? Math.max(0, Math.floor(up)) : 0,
    version: String(health.version || "unknown"),
  };
}

export async function getDiagnostics(): Promise<DiagnosticInfo> {
  const [health, metrics, shallow] = await Promise.all([
    fetchSystemHealth().catch(() => ({} as SystemHealthPayload)),
    fetchSystemMetrics().catch(() => ({} as SystemMetricsPayload)),
    fetchHealth().catch(() => ({ ok: false })),
  ]);
  const base = mapSystemPayloadsToDiagnostics(health, metrics);
  if (!shallow.ok && base.api_status === "healthy") {
    return { ...base, api_status: "degraded" };
  }
  return base;
}
