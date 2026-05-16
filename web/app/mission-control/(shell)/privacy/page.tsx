"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type PrivacyPosture = {
  privacy_posture?: { mode?: string; local_first?: boolean; egress_guard_enabled?: boolean };
  egress_decisions?: { allowed?: number; blocked?: number };
  blocked_operations?: number;
  workflow_posture?: Array<{ workflow?: string; privacy_mode?: string }>;
};

export default function PrivacyPage() {
  const [data, setData] = useState<PrivacyPosture>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await apiFetch<PrivacyPosture>("/mission-control/privacy-posture"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const posture = data.privacy_posture ?? {};

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Privacy posture</h1>
        <p className="mt-1 text-sm text-muted-foreground">Operational privacy — not just configuration</p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2 text-sm">
        <div className="rounded border border-border/50 p-4">
          <p className="text-xs uppercase text-muted-foreground">Mode</p>
          <p className="font-mono mt-1">{posture.mode ?? "observe"}</p>
        </div>
        <div className="rounded border border-border/50 p-4">
          <p className="text-xs uppercase text-muted-foreground">Blocked operations</p>
          <p className="mt-1">{data.blocked_operations ?? 0}</p>
        </div>
        <div className="rounded border border-border/50 p-4">
          <p className="text-xs uppercase text-muted-foreground">Egress allowed / blocked</p>
          <p className="mt-1">
            {data.egress_decisions?.allowed ?? 0} / {data.egress_decisions?.blocked ?? 0}
          </p>
        </div>
      </div>
    </div>
  );
}
