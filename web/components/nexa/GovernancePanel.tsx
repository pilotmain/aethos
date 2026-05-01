"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { webDownloadBlob, webFetch, downloadBlobToFile } from "@/lib/api";
import type {
  EnterpriseChannelGovernanceOverview,
  GovernanceMe,
  GovernanceOrgOverview,
} from "@/lib/nexa-types";

export function GovernancePanel() {
  const [me, setMe] = useState<GovernanceMe | null>(null);
  const [meErr, setMeErr] = useState<string | null>(null);
  const [orgId, setOrgId] = useState("");
  const [overview, setOverview] = useState<GovernanceOrgOverview | null>(null);
  const [channelOverview, setChannelOverview] = useState<EnterpriseChannelGovernanceOverview | null>(null);
  const [channelNote, setChannelNote] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [meLoading, setMeLoading] = useState(true);

  const loadMe = useCallback(async () => {
    setMeLoading(true);
    setMeErr(null);
    try {
      const m = await webFetch<GovernanceMe>("/governance/me");
      setMe(m);
      if (m.governance_enabled) {
        const d = m.default_organization_id || m.organizations[0]?.id;
        if (d) {
          setOrgId((prev) => (prev.trim() ? prev : d));
        }
      }
    } catch (e) {
      setMe(null);
      setMeErr((e as Error).message);
    } finally {
      setMeLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  const loadOverview = useCallback(async () => {
    const o = orgId.trim();
    if (!o) {
      setErr("Enter an organization id");
      return;
    }
    setLoading(true);
    setErr(null);
    setChannelNote(null);
    setChannelOverview(null);
    try {
      const data = await webFetch<GovernanceOrgOverview>(`/governance/organizations/${encodeURIComponent(o)}/overview`);
      setOverview(data);
      try {
        const ch = await webFetch<EnterpriseChannelGovernanceOverview>(
          `/governance/overview?organization_id=${encodeURIComponent(o)}`,
        );
        setChannelOverview(ch);
      } catch {
        setChannelNote("Channel matrix and retention (admin UI) are only visible to users with owner/admin role.");
      }
    } catch (e) {
      setOverview(null);
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  const downloadExport = useCallback(
    async (format: "json" | "csv") => {
      const o = orgId.trim();
      if (!o) {
        setErr("Enter an organization id to export");
        return;
      }
      setErr(null);
      try {
        const ext = format === "json" ? "json" : "csv";
        const blob = await webDownloadBlob(
          `/governance/organizations/${encodeURIComponent(o)}/audit/export.${ext}`,
        );
        downloadBlobToFile(blob, `nexa-audit-${o}.${ext}`);
      } catch (e) {
        setErr((e as Error).message);
      }
    },
    [orgId],
  );

  if (meLoading) {
    return (
      <div className="mb-3 flex items-center gap-2 rounded border border-violet-500/20 bg-violet-500/[0.04] p-2.5 text-[10px] text-zinc-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading governance…
      </div>
    );
  }

  if (meErr) {
    return (
      <div className="mb-3 space-y-1 rounded border border-rose-500/30 bg-rose-500/10 p-2.5 text-[10px] text-rose-200/90">
        <p className="font-medium">Governance</p>
        <p>{meErr}</p>
      </div>
    );
  }

  if (me && !me.governance_enabled) {
    return (
      <div className="mb-3 space-y-1 rounded border border-zinc-600/40 bg-zinc-900/40 p-2.5 text-[10px] text-zinc-400">
        <p className="font-medium text-zinc-200">Governance (enterprise)</p>
        <p>
          Requires <span className="font-mono text-zinc-300">NEXA_GOVERNANCE_ENABLED=true</span> on the API. Current
          mode is single-user; no organization APIs are active.
        </p>
      </div>
    );
  }

  return (
    <div className="mb-3 space-y-2 rounded border border-violet-500/20 bg-violet-500/[0.04] p-2.5">
      <p className="text-[11px] font-medium text-zinc-200">Governance (enterprise)</p>
      <p className="text-[10px] text-zinc-500">
        Organizations, roles, and org-scoped audit. Default org from <span className="font-mono">NEXA_DEFAULT_ORGANIZATION_ID</span>{" "}
        is pre-filled when present. Exports require owner, admin, or auditor.
      </p>
      {me && me.governance_enabled && me.organizations.length === 0 && (
        <p className="text-[10px] text-amber-200/80">
          No organizations yet. Create one via <span className="font-mono">POST /governance/organizations</span> or enable{" "}
          <span className="font-mono">NEXA_AUTO_CREATE_DEFAULT_ORG</span> for local dev.
        </p>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-[8rem] flex-1 text-[10px] text-zinc-500">
          Organization id
          <input
            className="mt-0.5 w-full rounded border border-zinc-700 bg-zinc-900 px-1.5 py-1 font-mono text-[10px] text-zinc-200"
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            placeholder="org_…"
            autoComplete="off"
          />
        </label>
        <button
          type="button"
          disabled={loading}
          onClick={() => void loadOverview()}
          className="inline-flex items-center gap-1 rounded border border-violet-500/40 bg-violet-500/10 px-2 py-1 text-[10px] text-violet-200/90 hover:bg-violet-500/20 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
          Load overview
        </button>
        <button
          type="button"
          onClick={() => void downloadExport("json")}
          className="inline-flex items-center gap-0.5 rounded border border-zinc-600 px-2 py-1 text-[10px] text-zinc-300 hover:border-zinc-500"
        >
          <Download className="h-3 w-3" aria-hidden />
          Export audit JSON
        </button>
        <button
          type="button"
          onClick={() => void downloadExport("csv")}
          className="inline-flex items-center gap-0.5 rounded border border-zinc-600 px-2 py-1 text-[10px] text-zinc-300 hover:border-zinc-500"
        >
          <Download className="h-3 w-3" aria-hidden />
          Export audit CSV
        </button>
      </div>
      {err && <p className="text-[10px] text-rose-300/90">{err}</p>}
      {channelNote && <p className="text-[10px] text-zinc-500">{channelNote}</p>}
      {overview && !err && (
        <div className="mt-2 space-y-2 text-[10px] text-zinc-300">
          <p>
            <span className="text-zinc-500">Org</span>{" "}
            <span className="font-mono text-zinc-200">{overview.organization.id}</span>
            {" · "}
            <span className="text-zinc-500">{overview.organization.name}</span>
            {" · "}
            <span className="text-zinc-500">Your role</span>{" "}
            <span className="font-mono text-zinc-200">{overview.current_user_role}</span>
          </p>
          <div className="grid gap-1 sm:grid-cols-3">
            <div className="rounded border border-white/5 bg-black/20 px-2 py-1">
              <span className="text-zinc-500">Events 24h</span> {overview.audit_summary.events_24h}
            </div>
            <div className="rounded border border-white/5 bg-black/20 px-2 py-1">
              <span className="text-zinc-500">Permission requests</span> {overview.audit_summary.permission_requests}
            </div>
            <div className="rounded border border-white/5 bg-black/20 px-2 py-1">
              <span className="text-zinc-500">Denied</span> {overview.audit_summary.denied_actions}
            </div>
          </div>
          {overview.members && overview.members.length > 0 && (
            <div>
              <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">Members</p>
              <ul className="mt-1 max-h-32 list-disc space-y-0.5 overflow-y-auto pl-3.5">
                {overview.members.map((m) => (
                  <li key={m.user_id}>
                    <span className="font-mono text-zinc-200">{m.user_id}</span> — {m.role}
                    {!m.enabled ? " (disabled)" : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {overview.policies && Object.keys(overview.policies).length > 0 && (
            <div>
              <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">Effective policy (summary)</p>
              <pre className="mt-1 max-h-36 overflow-auto rounded border border-white/5 bg-black/30 p-1.5 text-[9px] text-zinc-400">
                {JSON.stringify(overview.policies, null, 2)}
              </pre>
            </div>
          )}
          {overview.recent_events && overview.recent_events.length > 0 && (
            <div>
              <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">Recent org-scoped events</p>
              <ul className="mt-1 max-h-36 space-y-1 overflow-y-auto">
                {(overview.recent_events as { event_type?: string; message?: string }[]).slice(0, 12).map((ev, i) => (
                  <li key={i} className="rounded border border-white/5 bg-black/20 px-1.5 py-1 text-[9px] text-zinc-400">
                    <span className="text-zinc-300">{ev.event_type}</span> — {(ev.message || "").slice(0, 120)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {channelOverview && !err && (
        <div className="mt-2 space-y-2 border-t border-white/5 pt-2 text-[10px] text-zinc-300">
          <p>
            <span className="text-zinc-500">Retention</span> {channelOverview.retention_days} days
            {" · "}
            <span className="font-mono text-zinc-500">{channelOverview.organization_id}</span>
          </p>
          {channelOverview.policies && channelOverview.policies.length > 0 && (
            <div>
              <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">Channel policies</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-3.5">
                {channelOverview.policies.map((p) => (
                  <li key={p.channel}>
                    <span className="font-mono text-zinc-200">{p.channel}</span> —{" "}
                    {p.enabled ? "enabled" : "disabled"} · roles: {(p.allowed_roles || []).join(", ") || "—"} ·
                    approval: {p.approval_required ? "yes" : "no"}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {channelOverview.channels && channelOverview.channels.length > 0 && (
            <div>
              <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">Channels (status + policy)</p>
              <ul className="mt-1 max-h-40 space-y-1 overflow-y-auto">
                {channelOverview.channels.map((c) => (
                  <li
                    key={c.channel}
                    className="rounded border border-white/5 bg-black/20 px-1.5 py-1 text-[9px] text-zinc-400"
                  >
                    <span className="text-zinc-200">{c.label}</span> — cfg {c.configured ? "ok" : "no"} · gov.{" "}
                    {c.governance_enabled == null ? "n/a" : c.governance_enabled ? "on" : "off"} · roles{" "}
                    {(c.allowed_roles ?? []).join(", ") || "—"} · appr. {String(c.approval_required ?? false)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
