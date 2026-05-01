"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  LayoutDashboard,
  Loader2,
  MessageSquareText,
  Radio,
  RefreshCw,
  Shield,
  Users,
  Wrench,
  XCircle,
} from "lucide-react";
import { webFetch } from "@/lib/api";
import { isConfigured } from "@/lib/config";
import { LuminousNode } from "@/components/mission-control/LuminousNode";
import { MaintenancePanel } from "@/components/mission-control/MaintenancePanel";
import { orchestrationToMissionMapGroups } from "@/components/mission-control/missionMap";
import type {
  CustomAgent,
  CustomAgentsListOut,
  MissionControlSummary,
  MissionControlItem,
  ReportsMissionControl,
  ReportsStatus,
} from "@/lib/nexa-types";

const SUMMARY_HOURS = 24;

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso.replace("Z", "")).getTime();
  if (Number.isNaN(t)) return "—";
  const sec = Math.round((Date.now() - t) / 1000);
  if (sec < 45) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 48) return `${hr}h ago`;
  return new Date(iso).toLocaleString();
}

function cardShell(children: ReactNode) {
  return (
    <div className="rounded-xl border border-white/10 bg-zinc-950/60 p-4 shadow-sm backdrop-blur-sm">{children}</div>
  );
}

function MissionMapStrip({ summary }: { summary: MissionControlSummary }) {
  const groups = orchestrationToMissionMapGroups(summary);
  if (groups.length === 0) return null;
  return (
    <div className="mb-4">
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-zinc-500">Mission map (live)</p>
      <div className="flex flex-col gap-4">
        {groups.map((g) => (
          <div key={g.groupKey}>
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
              <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-600">{g.heading}</p>
            </div>
            <div className="flex flex-wrap gap-3">
              {g.nodes.map((n) => (
                <div key={n.key} className="min-w-[140px] max-w-[220px] flex-1">
                  <LuminousNode handle={n.handle} status={n.status} label={n.label} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MissionControlPage() {
  const [data, setData] = useState<MissionControlSummary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [permBusy, setPermBusy] = useState<number | null>(null);
  const [customAgents, setCustomAgents] = useState<CustomAgent[] | null>(null);
  /** Start true so we do not flash “No custom agents” before the first fetch. */
  const [customAgentsLoading, setCustomAgentsLoading] = useState(true);
  const [customAgentsErr, setCustomAgentsErr] = useState<string | null>(null);
  const [agentBusy, setAgentBusy] = useState<string | null>(null);
  const [assignmentBusy, setAssignmentBusy] = useState<number | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [jobRowBusy, setJobRowBusy] = useState<number | null>(null);
  const [attentionBusyId, setAttentionBusyId] = useState<string | null>(null);
  const [resetBusy, setResetBusy] = useState(false);
  const [purgeBusy, setPurgeBusy] = useState(false);
  const [sqlHardBusy, setSqlHardBusy] = useState(false);
  const [maintenanceOpen, setMaintenanceOpen] = useState(false);
  const [wsReport, setWsReport] = useState<string | null>(null);
  const [wsReportErr, setWsReportErr] = useState<string | null>(null);
  const [wsReportUpdated, setWsReportUpdated] = useState<string | null>(null);
  const lastReportMtimeRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    if (!isConfigured()) {
      setErr("Configure API base and user id on the login page.");
      setLoading(false);
      setCustomAgents(null);
      setCustomAgentsErr(null);
      setCustomAgentsLoading(false);
      return;
    }
    setErr(null);
    setLoading(true);
    setCustomAgentsLoading(true);
    setCustomAgentsErr(null);
    try {
      const [summaryRes, agentsRes] = await Promise.allSettled([
        webFetch<MissionControlSummary>(`/mission-control/summary?hours=${SUMMARY_HOURS}`),
        webFetch<CustomAgentsListOut>(`/custom-agents`),
      ]);
      if (summaryRes.status === "fulfilled") {
        setData(summaryRes.value);
      } else {
        setData(null);
        const r = summaryRes.reason;
        setErr(r instanceof Error ? r.message : String(r));
      }
      if (agentsRes.status === "fulfilled") {
        setCustomAgents(agentsRes.value.agents);
        setCustomAgentsErr(null);
      } else {
        setCustomAgents([]);
        const r = agentsRes.reason;
        setCustomAgentsErr(r instanceof Error ? r.message : String(r));
      }
    } finally {
      setLoading(false);
      setCustomAgentsLoading(false);
    }
  }, []);

  const onClearWorkspaceReport = async () => {
    setErr(null);
    setReportBusy(true);
    setNotice(null);
    try {
      await webFetch(`/mission-control/reports/clear`, { method: "POST" });
      setNotice("Workspace report cleared.");
      lastReportMtimeRef.current = null;
      await load();
      try {
        const mc = await webFetch<ReportsMissionControl>(`/reports/mission-control`);
        setWsReport(mc.markdown);
        setWsReportUpdated(
          mc.mission_control_mtime != null
            ? new Date(mc.mission_control_mtime * 1000).toISOString()
            : null
        );
      } catch {
        /* ignore */
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setReportBusy(false);
    }
  };

  const onCancelAssignment = async (assignmentId: number) => {
    setErr(null);
    setAssignmentBusy(assignmentId);
    setNotice(null);
    try {
      await webFetch(`/mission-control/assignments/${assignmentId}/cancel`, { method: "POST" });
      setNotice(`Cancelled assignment #${assignmentId}.`);
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setAssignmentBusy(null);
    }
  };

  const onDeleteAssignment = async (assignmentId: number) => {
    if (!window.confirm(`Remove assignment #${assignmentId} from Mission Control?`)) return;
    setErr(null);
    setAssignmentBusy(assignmentId);
    setNotice(null);
    try {
      await webFetch(`/mission-control/assignments/${assignmentId}/delete`, { method: "POST" });
      setNotice(`Removed assignment #${assignmentId}.`);
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setAssignmentBusy(null);
    }
  };

  const onDismissAttention = async (itemId: string) => {
    setErr(null);
    setAttentionBusyId(itemId);
    setNotice(null);
    try {
      await webFetch(`/mission-control/attention/${encodeURIComponent(itemId)}/dismiss`, {
        method: "POST",
      });
      setNotice("Item dismissed.");
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setAttentionBusyId(null);
    }
  };

  const onDismissJob = async (jobId: number) => {
    setErr(null);
    setJobRowBusy(jobId);
    setNotice(null);
    try {
      await webFetch(`/mission-control/jobs/${jobId}/dismiss`, { method: "POST" });
      setNotice(`Dismissed job #${jobId}.`);
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setJobRowBusy(null);
    }
  };

  const onDeleteJob = async (jobId: number) => {
    if (!window.confirm(`Remove job #${jobId} from Mission Control?`)) return;
    setErr(null);
    setJobRowBusy(jobId);
    setNotice(null);
    try {
      await webFetch(`/mission-control/jobs/${jobId}/delete`, { method: "POST" });
      setNotice(`Removed job #${jobId}.`);
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setJobRowBusy(null);
    }
  };

  const onDeleteCustomAgentMc = async (handle: string) => {
    if (!window.confirm(`Delete @${handle} from Mission Control?`)) return;
    setErr(null);
    setAgentBusy(handle);
    setNotice(null);
    try {
      await webFetch(`/mission-control/custom-agents/${encodeURIComponent(handle)}/delete`, {
        method: "POST",
      });
      setNotice(`Disabled @${handle}.`);
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setAgentBusy(null);
    }
  };

  const refreshReportsAfterMaintenance = async () => {
    lastReportMtimeRef.current = null;
    await load();
    try {
      const mc = await webFetch<ReportsMissionControl>(`/reports/mission-control`);
      setWsReport(mc.markdown);
      setWsReportUpdated(
        mc.mission_control_mtime != null
          ? new Date(mc.mission_control_mtime * 1000).toISOString()
          : null
      );
    } catch {
      /* ignore */
    }
  };

  const performResetVisible = async (opts: { includeCustomAgents: boolean }) => {
    setErr(null);
    setResetBusy(true);
    setNotice(null);
    try {
      await webFetch(`/mission-control/reset`, {
        method: "POST",
        body: JSON.stringify({
          include_custom_agents: opts.includeCustomAgents,
          hard_delete: false,
        }),
      });
      setNotice("Mission Control reset.");
      await refreshReportsAfterMaintenance();
    } catch (e) {
      const msg = (e as Error).message;
      setErr(msg);
      throw e;
    } finally {
      setResetBusy(false);
    }
  };

  const performPurgeEverything = async () => {
    setErr(null);
    setPurgeBusy(true);
    setNotice(null);
    try {
      await webFetch(`/mission-control/purge`, {
        method: "POST",
        body: JSON.stringify({ hard_delete: false }),
      });
      setNotice("Mission Control fully cleared (all custom agents disabled).");
      await refreshReportsAfterMaintenance();
    } catch (e) {
      const msg = (e as Error).message;
      setErr(msg);
      throw e;
    } finally {
      setPurgeBusy(false);
    }
  };

  const performHardSqlErase = async () => {
    setErr(null);
    setSqlHardBusy(true);
    setNotice(null);
    try {
      await webFetch(`/mission-control/reset-hard`, {
        method: "POST",
        body: JSON.stringify({
          include_audit_logs: false,
          include_pending_permissions: true,
          include_custom_agents: true,
          clear_workspace_files: true,
        }),
      });
      setNotice("Database hard erase completed (SQL purge).");
      await refreshReportsAfterMaintenance();
    } catch (e) {
      const msg = (e as Error).message;
      setErr(msg);
      throw e;
    } finally {
      setSqlHardBusy(false);
    }
  };

  const onToggleCustomAgent = async (handle: string, enabled: boolean) => {
    setErr(null);
    setAgentBusy(handle);
    setNotice(null);
    try {
      await webFetch(`/custom-agents/${encodeURIComponent(handle)}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      });
      setNotice(enabled ? `Enabled @${handle}.` : `Disabled @${handle}.`);
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setAgentBusy(null);
    }
  };

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!isConfigured()) return undefined;
    let cancelled = false;
    const poll = async () => {
      try {
        const st = await webFetch<ReportsStatus>(`/reports/status`);
        if (cancelled) return;
        const m = st.mission_control_mtime;
        const shouldFetch = m == null ? lastReportMtimeRef.current === null : lastReportMtimeRef.current !== m;
        if (shouldFetch) {
          if (m != null) lastReportMtimeRef.current = m;
          const mc = await webFetch<ReportsMissionControl>(`/reports/mission-control`);
          if (!cancelled) {
            setWsReport(mc.markdown);
            setWsReportErr(null);
            setWsReportUpdated(
              mc.mission_control_mtime != null
                ? new Date(mc.mission_control_mtime * 1000).toISOString()
                : null
            );
          }
        }
      } catch (e) {
        if (!cancelled) {
          setWsReportErr((e as Error).message);
        }
      }
    };
    void poll();
    const id = setInterval(() => void poll(), 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  type GrantMode = "once" | "session" | "always_workspace" | "always_repo_branch";

  const grantNotice = (mode: GrantMode): string => {
    switch (mode) {
      case "once":
        return "Allowed once.";
      case "session":
        return "Allowed for this session.";
      case "always_workspace":
        return "Allowed for this workspace (long-lived).";
      case "always_repo_branch":
        return "Allowed for this repo/branch context (long-lived).";
      default:
        return "Permission updated.";
    }
  };

  const onGrant = async (permissionId: number, mode: GrantMode) => {
    setErr(null);
    setPermBusy(permissionId);
    setNotice(null);
    try {
      const body =
        mode === "session"
          ? { grant_mode: "session", grant_session_hours: 8 }
          : { grant_mode: mode };
      await webFetch(`/web/access/permissions/${permissionId}/grant`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setNotice(grantNotice(mode));
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setPermBusy(null);
    }
  };

  const onDeny = async (permissionId: number) => {
    setErr(null);
    setPermBusy(permissionId);
    setNotice(null);
    try {
      await webFetch(`/permissions/requests/${permissionId}/deny`, {
        method: "POST",
      });
      setNotice("Permission denied.");
      await load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setPermBusy(null);
    }
  };

  const ov = data?.overview;
  const counts = (data?.risk_summary?.counts ?? {}) as Record<string, number>;

  return (
    <div className="min-h-screen bg-[#060608] text-zinc-200">
      <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
        <header className="mb-8 flex flex-col gap-3 border-b border-white/10 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-violet-400/90">
              Nexa
            </p>
            <h1 className="mt-1 flex items-center gap-2 text-2xl font-semibold tracking-tight text-zinc-50">
              <LayoutDashboard className="h-7 w-7 text-violet-400/90" aria-hidden />
              Mission Control
            </h1>
            <p className="mt-2 max-w-xl text-sm text-zinc-500">
              Priorities, approvals, and active work — one place to see what needs attention without leaving chat
              behind.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/"
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-medium text-zinc-200 hover:border-zinc-500"
            >
              Chat
              <ArrowRight className="h-3.5 w-3.5 opacity-70" aria-hidden />
            </Link>
            <Link
              href="/trust"
              className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-200/95 hover:bg-emerald-500/20"
            >
              <Shield className="h-3.5 w-3.5" aria-hidden />
              Trust & activity
            </Link>
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-medium text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Refresh
            </button>
            <button
              type="button"
              onClick={() => setMaintenanceOpen(true)}
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-600 bg-zinc-900/80 px-3 py-2 text-xs font-medium text-zinc-400 hover:border-violet-500/40 hover:text-zinc-200"
            >
              <Wrench className="h-3.5 w-3.5 opacity-80" aria-hidden />
              Maintenance
            </button>
          </div>
        </header>

        <MaintenancePanel
          open={maintenanceOpen}
          onOpenChange={setMaintenanceOpen}
          sqlPurgeEnabled={Boolean(data?.maintenance?.sql_purge_enabled)}
          busyReset={resetBusy}
          busyPurge={purgeBusy}
          busyHardSql={sqlHardBusy}
          onResetVisible={performResetVisible}
          onHardErase={performHardSqlErase}
          onDeleteEverything={performPurgeEverything}
        />

        {(notice || err || (loading && data)) && (
          <div className="mb-6 space-y-2" aria-live="polite">
            {notice ? (
              <p className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100/90">
                {notice}
              </p>
            ) : null}
            {err ? (
              <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-100/90">
                {err}
              </p>
            ) : null}
            {loading && data ? (
              <p className="flex items-center gap-2 text-xs text-zinc-500">
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                Refreshing Mission Control…
              </p>
            ) : null}
          </div>
        )}

        {isConfigured() && (
          <section className="mb-10">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
              <Radio className="h-4 w-4 text-cyan-400/80" aria-hidden />
              Workspace report
            </h2>
            {cardShell(
              <div>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-zinc-500">
                    File-backed <code className="text-zinc-400">mission_control.md</code> (
                    {wsReportUpdated ? `updated ${formatWhen(wsReportUpdated)}` : "polling every 5s"}).
                  </p>
                  <button
                    type="button"
                    disabled={reportBusy}
                    onClick={() => void onClearWorkspaceReport()}
                    className="shrink-0 rounded border border-cyan-500/35 bg-cyan-500/10 px-3 py-1.5 text-[11px] font-medium text-cyan-100/95 hover:bg-cyan-500/20 disabled:opacity-50"
                  >
                    {reportBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Clear workspace report"}
                  </button>
                </div>
                {wsReportErr && <p className="text-sm text-amber-400">{wsReportErr}</p>}
                {wsReport === null && !wsReportErr && (
                  <p className="text-sm text-zinc-500">Loading workspace report…</p>
                )}
                {wsReport !== null && (
                  <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/40 p-3 text-xs text-zinc-300">
                    {wsReport || "(empty)"}
                  </pre>
                )}
              </div>
            )}
          </section>
        )}

        {isConfigured() && (
          <section className="mb-10">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
              <Bot className="h-4 w-4 text-violet-400/80" aria-hidden />
              Custom agents
            </h2>
            {customAgentsLoading && customAgents === null ? (
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Loading agents…
              </div>
            ) : (
              <>
                {customAgentsErr ? (
                  <p className="mb-3 rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-100/90">
                    Could not load custom agents: {customAgentsErr}
                  </p>
                ) : null}
                {(customAgents?.length ?? 0) === 0 && !customAgentsErr ? (
                  <div className="rounded-xl border border-white/10 bg-zinc-950/60 p-4 text-sm text-zinc-400">
                    <p>No custom agents yet.</p>
                    <p className="mt-2 text-[12px] leading-relaxed text-zinc-500">
                      Create one in chat, e.g.{" "}
                      <code className="rounded bg-black/40 px-1 py-px font-mono text-[11px] text-emerald-200/90">
                        Create me a custom agent called @research-analyst …
                      </code>
                    </p>
                  </div>
                ) : null}
                {customAgents && customAgents.length > 0 ? (
                  <ul className="space-y-3">
                    {customAgents.map((agent) => {
                      const regulated =
                        (agent.safety_level || "").toLowerCase() === "regulated";
                      return (
                        <li key={agent.handle}>
                          {cardShell(
                            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="font-mono text-sm font-medium text-zinc-100">
                                    @{agent.handle}
                                  </span>
                                  <span
                                    className={`rounded border px-2 py-0.5 text-[10px] font-medium ${
                                      agent.enabled
                                        ? "border-emerald-500/35 bg-emerald-500/15 text-emerald-100/95"
                                        : "border-zinc-600 bg-zinc-800/80 text-zinc-400"
                                    }`}
                                  >
                                    {agent.enabled ? "Enabled" : "Disabled"}
                                  </span>
                                  <span className="rounded border border-white/10 px-2 py-0.5 text-[10px] text-zinc-400">
                                    {regulated ? "Regulated" : "Standard"}
                                  </span>
                                </div>
                                {agent.display_name ? (
                                  <p className="mt-1 text-xs text-zinc-500">{agent.display_name}</p>
                                ) : null}
                                <p className="mt-2 line-clamp-4 text-xs text-zinc-400">
                                  {agent.description?.trim() || "No description"}
                                </p>
                              </div>
                              <div className="flex shrink-0 flex-wrap gap-2">
                                <button
                                  type="button"
                                  disabled={agentBusy === agent.handle}
                                  onClick={() =>
                                    void onToggleCustomAgent(agent.handle, !agent.enabled)
                                  }
                                  className="rounded border border-zinc-600 bg-zinc-900 px-3 py-1.5 text-[11px] font-medium text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
                                >
                                  {agentBusy === agent.handle ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  ) : agent.enabled ? (
                                    "Disable"
                                  ) : (
                                    "Enable"
                                  )}
                                </button>
                                <Link
                                  href={`/?draft=${encodeURIComponent(`describe @${agent.handle}`)}`}
                                  className="inline-flex items-center gap-1 rounded border border-violet-500/35 bg-violet-500/10 px-3 py-1.5 text-[11px] font-medium text-violet-100/95 hover:bg-violet-500/20"
                                >
                                  <MessageSquareText className="h-3.5 w-3.5" aria-hidden />
                                  Describe
                                </Link>
                                <button
                                  type="button"
                                  disabled={agentBusy === agent.handle}
                                  onClick={() => void onDeleteCustomAgentMc(agent.handle)}
                                  className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-[11px] font-medium text-rose-100 hover:bg-rose-500/20 disabled:opacity-50"
                                >
                                  Delete
                                </button>
                              </div>
                            </div>,
                          )}
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </>
            )}
          </section>
        )}

        {isConfigured() && data?.orchestration && (
          <section className="mb-10">
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
              <Users className="h-4 w-4 text-cyan-400/80" aria-hidden />
              Agent team & assignments
            </h2>
            <MissionMapStrip summary={data} />
            {cardShell(
              <div className="space-y-3 text-sm">
                {data.orchestration.organization ? (
                  <p className="text-zinc-400">
                    Organization{" "}
                    <span className="font-mono text-zinc-200">
                      #{data.orchestration.organization.id}
                    </span>{" "}
                    · {data.orchestration.organization.name}
                  </p>
                ) : (
                  <p className="text-zinc-500">
                    No agent organization yet — say{" "}
                    <code className="rounded bg-black/40 px-1 py-px font-mono text-[11px] text-cyan-200/90">
                      create an agent team
                    </code>{" "}
                    in chat.
                  </p>
                )}
                {(data.orchestration.roles?.length ?? 0) > 0 ? (
                  <ul className="space-y-1 border-t border-white/10 pt-3 text-xs text-zinc-400">
                    {data.orchestration.roles.map((r) => (
                      <li key={`${r.agent_handle}-${r.role}`} className="flex flex-wrap gap-2">
                        <span className="font-mono text-zinc-200">
                          @
                          {r.agent_handle_display ??
                            r.agent_handle.replace(/_/g, "-")}
                        </span>
                        <span>{r.role}</span>
                        {r.reports_to_handle ? (
                          <span className="text-zinc-500">
                            → reports to @
                            {r.reports_to_handle_display ??
                              r.reports_to_handle.replace(/_/g, "-")}
                          </span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {(data.orchestration.assignments?.length ?? 0) === 0 ? (
                  <p className="text-xs text-zinc-500">No assignments yet.</p>
                ) : (
                  <ul className="space-y-2 border-t border-white/10 pt-3">
                    {data.orchestration.assignments.map((a) => (
                      <li
                        key={a.id}
                        className="flex flex-wrap items-start justify-between gap-2 text-xs"
                      >
                        <span className="min-w-0 text-zinc-300">
                          <span className="font-mono text-zinc-100">#{a.id}</span>{" "}
                          <span className="text-zinc-500">
                            @
                            {a.assigned_to_handle_display ??
                              a.assigned_to_handle.replace(/_/g, "-")}
                          </span>{" "}
                          — {a.title}
                          {a.cursor_run_id ? (
                            <span className="mt-1 block font-mono text-[10px] text-violet-400/90">
                              Cursor {a.cursor_status ?? "—"} · {a.cursor_repo ?? "repo"} @{" "}
                              {a.cursor_branch ?? "branch"} · run {a.cursor_run_id}
                            </span>
                          ) : null}
                        </span>
                        <div className="flex shrink-0 flex-wrap items-center gap-2">
                          <span className="rounded border border-white/10 px-2 py-0.5 text-[10px] uppercase text-zinc-400">
                            {a.status}
                          </span>
                          <button
                            type="button"
                            disabled={assignmentBusy === a.id}
                            onClick={() => void onCancelAssignment(a.id)}
                            className="rounded border border-zinc-600 bg-zinc-900 px-2 py-1 text-[10px] font-medium text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
                          >
                            {assignmentBusy === a.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              "Cancel"
                            )}
                          </button>
                          <button
                            type="button"
                            disabled={assignmentBusy === a.id}
                            onClick={() => void onDeleteAssignment(a.id)}
                            className="rounded border border-rose-500/40 bg-rose-500/10 px-2 py-1 text-[10px] font-medium text-rose-100 hover:bg-rose-500/20 disabled:opacity-50"
                          >
                            Delete
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>,
            )}
          </section>
        )}

        {loading && !data && (
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading Mission Control…
          </div>
        )}

        {data && ov && (
          <>
            <section className="mb-10">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">Overview</h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                {(
                  [
                    ["Active jobs", ov.active_jobs, Radio],
                    ["Pending approvals", ov.pending_approvals, AlertTriangle],
                    ["Blocked actions", ov.blocked_actions, XCircle],
                    ["High risk", ov.high_risk_events, AlertTriangle],
                    ["Channels ready", ov.active_channels, CheckCircle2],
                    ["Recent executions", ov.recent_executions, Shield],
                  ] as const
                ).map(([label, value, Icon]) => (
                  <div key={label}>
                    {cardShell(
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">{label}</p>
                          <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-50">{value}</p>
                        </div>
                        <Icon className="h-5 w-5 shrink-0 text-zinc-600" aria-hidden />
                      </div>,
                    )}
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[10px] text-zinc-600">
                Window: last {data.hours ?? SUMMARY_HOURS}h · counts reflect your Nexa user id only.
              </p>
            </section>

            {data.quiet && (
              <section className="mb-10 rounded-xl border border-zinc-800 bg-zinc-950/40 px-4 py-6 text-center">
                <p className="text-sm font-medium text-zinc-300">Mission Control is quiet.</p>
                <p className="mt-2 text-sm text-zinc-500">
                  Run a workflow, approve an action, or connect a channel to see priorities here.
                </p>
              </section>
            )}

            <section className="mb-10">
              <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Attention queue
              </h2>
              {data.attention.length === 0 ? (
                <p className="text-sm text-zinc-500">Nothing queued.</p>
              ) : (
                <ul className="space-y-2">
                  {data.attention.map((item: MissionControlItem) => (
                    <li key={item.id}>
                      {cardShell(
                        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-zinc-100">{item.title}</p>
                            {item.description ? (
                              <p className="mt-1 line-clamp-3 text-xs text-zinc-500">{item.description}</p>
                            ) : null}
                            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-zinc-500">
                              <span className="rounded border border-white/10 px-1.5 py-px font-mono text-zinc-400">
                                {item.type.replace(/_/g, " ")}
                              </span>
                              {item.status ? <span>status {item.status}</span> : null}
                              {item.risk_level ? <span>risk {item.risk_level}</span> : null}
                              {item.channel ? <span>channel {item.channel}</span> : null}
                              <span>{formatWhen(item.created_at)}</span>
                              {item.score != null ? <span>score {item.score}</span> : null}
                            </div>
                          </div>
                          <div className="flex shrink-0 flex-col items-end gap-2">
                            <div className="flex flex-wrap justify-end gap-2">
                              <button
                                type="button"
                                disabled={
                                  attentionBusyId === item.id ||
                                  (item.job_id != null && jobRowBusy === item.job_id)
                                }
                                onClick={() =>
                                  void (item.job_id != null &&
                                  (item.type === "failed_job" || item.type === "running_job")
                                    ? onDismissJob(item.job_id!)
                                    : onDismissAttention(item.id))
                                }
                                className="rounded border border-zinc-600 bg-zinc-900 px-2 py-1 text-[10px] font-medium text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
                              >
                                {attentionBusyId === item.id ||
                                (item.job_id != null && jobRowBusy === item.job_id) ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  "Dismiss"
                                )}
                              </button>
                              {item.job_id != null &&
                              (item.type === "failed_job" || item.type === "running_job") ? (
                                <button
                                  type="button"
                                  disabled={jobRowBusy === item.job_id}
                                  onClick={() => void onDeleteJob(item.job_id!)}
                                  className="rounded border border-rose-500/40 bg-rose-500/10 px-2 py-1 text-[10px] font-medium text-rose-100 hover:bg-rose-500/20 disabled:opacity-50"
                                >
                                  Delete
                                </button>
                              ) : null}
                            </div>
                            <Link
                              href="/trust"
                              className="text-[10px] font-medium text-emerald-400/90 hover:underline"
                            >
                              Trust detail →
                            </Link>
                          </div>
                        </div>,
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="mb-10">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">Active work</h2>
              {data.active_work.length === 0 ? (
                <p className="text-sm text-zinc-500">No in-flight jobs.</p>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-white/10">
                  <table className="w-full min-w-[640px] text-left text-xs">
                    <thead className="border-b border-white/10 bg-black/30 text-[10px] uppercase tracking-wide text-zinc-500">
                      <tr>
                        <th className="px-3 py-2">Job</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Agent</th>
                        <th className="px-3 py-2">Channel</th>
                        <th className="px-3 py-2">Updated</th>
                        <th className="px-3 py-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {data.active_work.map((j: MissionControlItem) => (
                        <tr key={j.id} className="hover:bg-white/[0.02]">
                          <td className="px-3 py-2 font-mono text-zinc-300">
                            #{j.job_id}{" "}
                            <span className="font-sans text-zinc-400">{j.title}</span>
                          </td>
                          <td className="px-3 py-2 text-zinc-400">{j.status}</td>
                          <td className="px-3 py-2 text-zinc-400">{j.agent ?? "—"}</td>
                          <td className="px-3 py-2 text-zinc-400">{j.channel ?? "—"}</td>
                          <td className="px-3 py-2 text-zinc-500">{formatWhen(j.updated_at ?? j.created_at)}</td>
                          <td className="px-3 py-2 text-right">
                            <div className="flex flex-wrap justify-end gap-1">
                              {j.job_id != null ? (
                                <>
                                  <button
                                    type="button"
                                    disabled={jobRowBusy === j.job_id}
                                    onClick={() => void onDismissJob(j.job_id!)}
                                    className="rounded border border-zinc-600 bg-zinc-900 px-2 py-1 text-[10px] text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
                                  >
                                    Dismiss
                                  </button>
                                  <button
                                    type="button"
                                    disabled={jobRowBusy === j.job_id}
                                    onClick={() => void onDeleteJob(j.job_id!)}
                                    className="rounded border border-rose-500/40 bg-rose-500/10 px-2 py-1 text-[10px] text-rose-100 hover:bg-rose-500/20 disabled:opacity-50"
                                  >
                                    Delete
                                  </button>
                                </>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="mb-10">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Pending approvals
              </h2>
              {data.pending_approvals.length === 0 ? (
                <p className="text-sm text-zinc-500">No pending permission requests.</p>
              ) : (
                <ul className="space-y-3">
                  {data.pending_approvals.map((p: MissionControlItem) => (
                    <li key={p.id}>
                      {cardShell(
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-zinc-100">{p.scope ?? "Permission"}</p>
                            <p className="mt-1 break-all font-mono text-[11px] text-zinc-400">{p.target}</p>
                            {p.reason ? (
                              <p className="mt-2 text-xs text-zinc-500">{p.reason}</p>
                            ) : null}
                            <p className="mt-2 text-[10px] text-zinc-600">
                              Risk {p.risk_level ?? "—"} · {p.channel ?? "web"} · {formatWhen(p.created_at)}
                            </p>
                          </div>
                          {p.permission_id != null ? (
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                disabled={attentionBusyId === p.id || permBusy === p.permission_id}
                                onClick={() => void onDismissAttention(p.id)}
                                className="rounded border border-zinc-600 bg-zinc-900 px-3 py-1.5 text-[11px] font-medium text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
                              >
                                {attentionBusyId === p.id ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  "Dismiss"
                                )}
                              </button>
                              <button
                                type="button"
                                disabled={permBusy === p.permission_id}
                                onClick={() => void onGrant(p.permission_id!, "once")}
                                className="rounded border border-emerald-500/40 bg-emerald-500/15 px-3 py-1.5 text-[11px] font-medium text-emerald-100 hover:bg-emerald-500/25 disabled:opacity-50"
                              >
                                Allow once
                              </button>
                              <button
                                type="button"
                                disabled={permBusy === p.permission_id}
                                onClick={() => void onGrant(p.permission_id!, "session")}
                                className="rounded border border-cyan-500/40 bg-cyan-500/15 px-3 py-1.5 text-[11px] font-medium text-cyan-100 hover:bg-cyan-500/25 disabled:opacity-50"
                              >
                                Allow session
                              </button>
                              <button
                                type="button"
                                disabled={permBusy === p.permission_id}
                                onClick={() => void onGrant(p.permission_id!, "always_workspace")}
                                className="rounded border border-violet-500/35 bg-violet-500/10 px-3 py-1.5 text-[11px] font-medium text-violet-100 hover:bg-violet-500/20 disabled:opacity-50"
                              >
                                Always workspace
                              </button>
                              <button
                                type="button"
                                disabled={permBusy === p.permission_id}
                                onClick={() => void onGrant(p.permission_id!, "always_repo_branch")}
                                className="rounded border border-indigo-500/35 bg-indigo-500/10 px-3 py-1.5 text-[11px] font-medium text-indigo-100 hover:bg-indigo-500/20 disabled:opacity-50"
                              >
                                Always repo branch
                              </button>
                              <button
                                type="button"
                                disabled={permBusy === p.permission_id}
                                onClick={() => void onDeny(p.permission_id!)}
                                className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-[11px] font-medium text-rose-100 hover:bg-rose-500/20 disabled:opacity-50"
                              >
                                Deny
                              </button>
                            </div>
                          ) : null}
                        </div>,
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="mb-10">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Risk & trust summary
              </h2>
              {cardShell(
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <div>
                    <p className="text-[10px] uppercase text-zinc-500">Blocked sends</p>
                    <p className="mt-1 text-lg font-semibold text-zinc-100">
                      {counts.network_external_send_blocked ?? 0}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase text-zinc-500">Sensitive warnings</p>
                    <p className="mt-1 text-lg font-semibold text-zinc-100">
                      {counts.sensitive_egress_warnings ?? 0}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase text-zinc-500">Permission uses</p>
                    <p className="mt-1 text-lg font-semibold text-zinc-100">{counts.permission_uses ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase text-zinc-500">Host blocks</p>
                    <p className="mt-1 text-lg font-semibold text-zinc-100">
                      {counts.host_executor_blocks ?? 0}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase text-zinc-500">Enforcement paths</p>
                    <p className="mt-1 text-lg font-semibold text-zinc-100">
                      {counts.safety_enforcement_paths ?? 0}
                    </p>
                  </div>
                </div>,
              )}
              <p className="mt-2 text-[11px] text-zinc-500">
                Same aggregates as{" "}
                <Link href="/trust" className="text-emerald-400/90 underline-offset-2 hover:underline">
                  Trust & activity
                </Link>
                .
              </p>
            </section>

            <section className="mb-10">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">Channel activity</h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {data.channels.map((ch) => (
                  <div key={ch.channel}>
                    {cardShell(
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium text-zinc-100">{ch.label}</p>
                          <p className="mt-1 text-[10px] text-zinc-500">
                            {ch.configured ? "Configured" : "Not configured"} · health {ch.health}
                          </p>
                        </div>
                        <span className="rounded border border-white/10 px-2 py-0.5 text-[10px] text-zinc-400">
                          {ch.recent_event_count ?? 0} events
                        </span>
                      </div>,
                    )}
                  </div>
                ))}
              </div>
            </section>

            <section className="mb-16">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Recommended next actions
              </h2>
              {data.recommendations.length === 0 ? (
                <p className="text-sm text-zinc-500">No automated suggestions right now.</p>
              ) : (
                <ul className="space-y-2">
                  {data.recommendations.map((r: MissionControlItem) => (
                    <li key={r.id} className="rounded-lg border border-violet-500/15 bg-violet-500/[0.06] px-3 py-2">
                      <p className="text-sm font-medium text-zinc-100">{r.title}</p>
                      {r.description ? (
                        <p className="mt-1 text-xs text-zinc-500">{r.description}</p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
