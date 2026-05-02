"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getMissionState,
  refreshMissionControlStore,
  subscribeMissionStore,
} from "@/lib/state/missionControlStore";
import { isConfigured } from "@/lib/config";

export type PrivacyIndicator = {
  level: "safe" | "redacted" | "blocked";
  label: string;
  severity: number;
};

export type MissionControlSnapshot = {
  tasks?: Array<{
    mission_id?: string;
    agent_handle?: string;
    status?: string;
    duration_ms?: number | null;
  }>;
  privacy_indicator?: PrivacyIndicator;
  provider_transparency?: Record<string, unknown>;
  runtime?: {
    offline_mode?: boolean;
    strict_privacy_mode?: boolean;
    remote_providers_available?: boolean;
    external_calls_disabled?: boolean;
    integrity_alert_active?: boolean;
    integrity_banner_level?: "critical" | "warning" | null;
    user_privacy_mode?: "standard" | "strict" | "paranoid" | string;
    privacy_score?: number;
  };
  integrity_alerts?: Array<Record<string, unknown>>;
  privacy_audit?: {
    recent_overrides?: unknown[];
    privacy_score?: number;
  };
  metrics?: Record<string, unknown>;
  /** Phase 23 — dev workspace registry (from /mission-control/state). */
  dev_workspaces?: Array<{
    id: string;
    name?: string;
    repo_path?: string;
    status?: string;
    created_at?: string | null;
  }>;
  dev_runs?: Array<{
    id: string;
    workspace_id?: string;
    goal?: string;
    status?: string;
    created_at?: string | null;
    completed_at?: string | null;
    error?: string | null;
    pipeline?: unknown;
  }>;
  long_running_sessions?: Array<Record<string, unknown>>;
  scheduler_jobs?: Array<Record<string, unknown>>;
  channel_activity?: Array<Record<string, unknown>>;
  token_economy?: Record<string, unknown>;
  autonomous_tasks?: Array<Record<string, unknown>>;
  autonomy_decisions?: Array<Record<string, unknown>>;
  autonomy_feedback?: Array<Record<string, unknown>>;
  autonomy_execution_stats?: Record<string, unknown>;
  maintenance?: {
    sql_purge_enabled?: boolean;
  };
  /** Phase 46–47 — goals, agent intel, autonomy stability (Mission Control vNext). */
  phase46?: Record<string, unknown>;
};

function snapshotFromStore(): MissionControlSnapshot | null {
  const raw = getMissionState();
  if (!raw || typeof raw !== "object") return null;
  return raw as MissionControlSnapshot;
}

export function useMissionControlSnapshot(pollMs = 8000): {
  data: MissionControlSnapshot | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [data, setData] = useState<MissionControlSnapshot | null>(() =>
    isConfigured() ? snapshotFromStore() : null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!isConfigured()) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }
    setError(null);
    try {
      await refreshMissionControlStore();
      setData(snapshotFromStore());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    return subscribeMissionStore(() => {
      if (!isConfigured()) return;
      setData(snapshotFromStore());
    });
  }, []);

  useEffect(() => {
    if (!pollMs || pollMs < 2000) return;
    const id = window.setInterval(() => void refresh(), pollMs);
    return () => window.clearInterval(id);
  }, [pollMs, refresh]);

  return { data, loading, error, refresh };
}
