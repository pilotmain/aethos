/**
 * TEMPORARY diagnostic page — compare raw GET /api/v1/agents/list vs Mission Control CEO UI.
 * Remove when CEO dashboard rendering is fixed.
 */
"use client";

import { useEffect, useState } from "react";

import { defaultConfig, readConfig } from "@/lib/config";

type AgentRow = {
  id?: string;
  name?: string;
  domain?: string;
  status?: string;
  success_rate?: number;
  total_actions?: number;
};

export default function SimpleCEODiagnosticPage() {
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const c = readConfig();
    const userId =
      (typeof window !== "undefined" ? window.localStorage.getItem("aethos_user_id") : null)?.trim() ||
      c.userId.trim() ||
      "tg_8666826080";
    const token =
      (typeof window !== "undefined" ? window.localStorage.getItem("aethos_bearer_token") : null)?.trim() ||
      c.token.trim();
    const apiBase = (
      (typeof window !== "undefined" ? window.localStorage.getItem("aethos_api_base") : null)?.trim() ||
      c.apiBase ||
      defaultConfig.apiBase ||
      "http://127.0.0.1:8010"
    ).replace(/\/$/, "");

    const headers: Record<string, string> = {
      Accept: "application/json",
      "X-User-Id": userId,
    };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    fetch(`${apiBase}/api/v1/agents/list`, { headers, cache: "no-store" })
      .then(async (res) => {
        const text = await res.text();
        if (!res.ok) {
          throw new Error(`${res.status}: ${text.slice(0, 400)}`);
        }
        try {
          return JSON.parse(text) as { agents?: AgentRow[] };
        } catch {
          throw new Error("Response was not JSON");
        }
      })
      .then((data) => {
        setAgents(Array.isArray(data.agents) ? data.agents : []);
        setLoading(false);
      })
      .catch((err: unknown) => {
        console.error(err);
        setError(err instanceof Error ? err.message : "Fetch failed");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div className="p-4 text-zinc-100">Loading agents…</div>;
  }

  if (error) {
    return (
      <div className="p-4 text-rose-300">
        <p className="font-medium">Error</p>
        <pre className="mt-2 whitespace-pre-wrap text-sm">{error}</pre>
      </div>
    );
  }

  return (
    <div className="p-4 text-zinc-100">
      <p className="mb-2 text-xs text-zinc-500">
        Temporary diagnostic — raw <code className="text-zinc-400">GET /api/v1/agents/list</code>
      </p>
      <h1 className="mb-4 text-2xl font-bold">CEO Dashboard ({agents.length} agents)</h1>
      <div className="space-y-2">
        {agents.map((agent) => (
          <div key={agent.id ?? agent.name} className="rounded border border-zinc-700 p-3">
            <div className="font-bold">@{agent.name ?? "?"}</div>
            <div className="text-sm text-zinc-400">Domain: {agent.domain ?? "—"}</div>
            <div className="text-sm text-zinc-400">Status: {agent.status ?? "—"}</div>
            <div className="text-sm text-zinc-400">
              Success: {agent.success_rate ?? "—"}% ({agent.total_actions ?? 0} actions)
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
