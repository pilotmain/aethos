"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api/client";

type WorkspaceIntel = {
  project_count?: number;
  deployment_linked_count?: number;
  repair_active_count?: number;
  workspace_confidence?: { level?: string; message?: string };
  risk_signals?: Array<{ kind?: string; severity?: string; count?: number }>;
  research_continuity?: { active_chains?: number; chains?: Array<{ topic?: string; research_chain_id?: string }> };
  summaries?: Record<string, string>;
  projects?: Array<{ project_id?: string; risk_level?: string; confidence?: string }>;
};

type RiskPayload = {
  high_risk_projects?: unknown[];
  risk_signals?: unknown[];
};

export default function WorkspaceIntelligencePage() {
  const [intel, setIntel] = useState<WorkspaceIntel>({});
  const [risks, setRisks] = useState<RiskPayload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [wi, rk] = await Promise.all([
        apiFetch<WorkspaceIntel>("/mission-control/workspace-intelligence"),
        apiFetch<RiskPayload>("/mission-control/workspace-risks"),
      ]);
      setIntel(wi);
      setRisks(rk);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const summ = intel.summaries ?? {};

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Workspace intelligence</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Projects, risk, research continuity — runtime-backed
        </p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <div className="grid gap-3 sm:grid-cols-3 text-sm">
        <div className="rounded border border-border/50 p-4">
          <p className="text-xs uppercase text-muted-foreground">Projects</p>
          <p className="mt-1 text-lg font-medium">{intel.project_count ?? 0}</p>
        </div>
        <div className="rounded border border-border/50 p-4">
          <p className="text-xs uppercase text-muted-foreground">Confidence</p>
          <p className="mt-1">{intel.workspace_confidence?.level ?? "—"}</p>
        </div>
        <div className="rounded border border-border/50 p-4">
          <p className="text-xs uppercase text-muted-foreground">Research chains</p>
          <p className="mt-1">{intel.research_continuity?.active_chains ?? 0}</p>
        </div>
      </div>
      {(intel.risk_signals ?? []).length > 0 ? (
        <section className="rounded border border-border/50 p-4 text-sm">
          <h2 className="font-medium">Operational risk</h2>
          <ul className="mt-2 space-y-1 text-muted-foreground">
            {(intel.risk_signals ?? []).map((s, i) => (
              <li key={i}>
                {s.kind} — {s.severity}
                {s.count != null ? ` (${s.count})` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <section className="rounded border border-border/50 p-4 text-sm space-y-2">
        <h2 className="font-medium">Summaries</h2>
        {Object.entries(summ).map(([k, v]) => (
          <p key={k} className="text-muted-foreground">
            <span className="font-mono text-xs">{k}</span>: {v}
          </p>
        ))}
      </section>
      {(intel.projects ?? []).length > 0 ? (
        <section className="rounded border border-border/50 p-4 text-sm">
          <h2 className="font-medium">Projects</h2>
          <ul className="mt-2 space-y-1">
            {(intel.projects ?? []).slice(0, 12).map((p) => (
              <li key={p.project_id} className="text-muted-foreground">
                {p.project_id} — risk {p.risk_level}, confidence {p.confidence ?? "—"}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {(risks.high_risk_projects ?? []).length > 0 ? (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          {String((risks.high_risk_projects ?? []).length)} high-risk project(s) flagged
        </p>
      ) : null}
    </div>
  );
}
