"use client";

import { useCallback, useEffect, useState } from "react";
import { webFetch } from "@/lib/api";
import { isConfigured, readConfig } from "@/lib/config";

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

export function useMissionControlSnapshot(pollMs = 8000): {
  data: MissionControlSnapshot | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [data, setData] = useState<MissionControlSnapshot | null>(null);
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
      const uid = readConfig().userId;
      const snap = await webFetch<MissionControlSnapshot>(
        `/mission-control/state?user_id=${encodeURIComponent(uid)}`,
      );
      setData(snap);
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
    if (!pollMs || pollMs < 2000) return;
    const id = window.setInterval(() => void refresh(), pollMs);
    return () => window.clearInterval(id);
  }, [pollMs, refresh]);

  return { data, loading, error, refresh };
}
