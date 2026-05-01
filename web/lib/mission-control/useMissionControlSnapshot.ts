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
  };
  metrics?: Record<string, unknown>;
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
