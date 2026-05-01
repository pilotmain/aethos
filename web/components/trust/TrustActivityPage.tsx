"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Shield, XCircle } from "lucide-react";
import { fetchTrustActivity, fetchTrustSummary } from "@/lib/api";
import { isConfigured, readConfig } from "@/lib/config";
import type { TrustEventRow, TrustSummaryResponse, TrustUiStatus } from "@/lib/nexa-types";
import {
  channelBadgeLabel,
  matchesChannelFilter,
  type TrustChannelTab,
} from "@/lib/trust-channel";

const ACTIVITY_HOURS = 168;
const SUMMARY_HOURS = 24;

type FilterTab = "all" | "blocked" | "external" | "sensitive" | "permissions";

const TABS: { id: FilterTab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "blocked", label: "Blocked" },
  { id: "external", label: "External" },
  { id: "sensitive", label: "Sensitive" },
  { id: "permissions", label: "Permissions" },
];

function formatTimeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso.replace("Z", "")).getTime();
  if (Number.isNaN(t)) return "—";
  const sec = Math.round((Date.now() - t) / 1000);
  if (sec < 45) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.round(min / 60);
  if (hr < 48) return `${hr}h ago`;
  return new Date(iso).toLocaleString();
}

function humanActionLabel(eventType: string): string {
  const et = eventType || "";
  const map: Record<string, string> = {
    "network.external_send.allowed": "External send · allowed",
    "network.external_send.blocked": "External send · blocked",
    "access.sensitive_egress.warning": "Outbound body · sensitivity warning",
    "access.permission.used": "Permission · used",
    "access.permission.requested": "Permission · requested",
    "access.permission.granted": "Permission · granted",
    "access.permission.denied": "Permission · denied",
    "access.permission.revoked": "Permission · revoked",
    "access.host_executor.blocked": "Host action · blocked",
    "safety.enforcement.path": "Safety · enforcement checked",
    access_denied: "Surface · denied",
  };
  if (map[et]) return map[et];
  return et.replace(/^access\./, "").replace(/\./g, " · ") || et;
}

function filterEvents(events: TrustEventRow[], tab: FilterTab): TrustEventRow[] {
  if (tab === "all") return events;
  if (tab === "blocked") return events.filter((e) => e.status === "blocked");
  if (tab === "external") {
    return events.filter(
      (e) =>
        e.event_type.includes("network.external_send") ||
        e.event_type.includes("sensitive_egress") ||
        e.event_type.includes("access.sensitive_egress")
    );
  }
  if (tab === "sensitive") {
    return events.filter(
      (e) =>
        e.status === "warning" ||
        !!(e.sensitivity_level && String(e.sensitivity_level).toLowerCase() !== "none")
    );
  }
  if (tab === "permissions") {
    return events.filter((e) => e.event_type.startsWith("access.permission"));
  }
  return events;
}

function filterByChannel(events: TrustEventRow[], channelTab: TrustChannelTab): TrustEventRow[] {
  if (channelTab === "all") return events;
  return events.filter((e) => matchesChannelFilter(e.channel, channelTab));
}

function StatusIcon({ status }: { status: TrustUiStatus }) {
  if (status === "blocked") {
    return <XCircle className="h-5 w-5 shrink-0 text-rose-400/90" aria-hidden />;
  }
  if (status === "warning") {
    return <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400/90" aria-hidden />;
  }
  return <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400/90" aria-hidden />;
}

function ChannelOriginBadge({ channel }: { channel: string | null | undefined }) {
  const label = channelBadgeLabel(channel);
  return (
    <span
      className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] font-medium text-zinc-400"
      title="Where this event originated"
    >
      {label}
    </span>
  );
}

function StatusStrip({ status }: { status: TrustUiStatus }) {
  const cls =
    status === "blocked"
      ? "border-rose-500/35 bg-rose-500/10 text-rose-100"
      : status === "warning"
        ? "border-amber-500/35 bg-amber-500/10 text-amber-100"
        : "border-emerald-500/30 bg-emerald-500/10 text-emerald-100";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls}`}
    >
      <StatusIcon status={status} />
      {status}
    </span>
  );
}

function WhyPanel({ ev }: { ev: TrustEventRow }) {
  const md = ev.metadata || {};
  const rows: { k: string; v: string }[] = [];

  const push = (label: string, val: unknown) => {
    if (val === undefined || val === null || val === "") return;
    const s = typeof val === "string" ? val : JSON.stringify(val);
    rows.push({ k: label, v: s.length > 600 ? `${s.slice(0, 600)}…` : s });
  };

  push("Instruction source", md.instruction_source);
  push("Permission scope", md.permission_scope_used);
  const sens = ev.sensitivity_level ?? md.sensitivity_level;
  if (sens !== undefined && sens !== null && String(sens).toLowerCase() !== "none") {
    push("Sensitivity", sens);
  }
  push("Policy version", md.nexa_safety_policy_version);
  const sha = md.nexa_safety_policy_sha256;
  if (typeof sha === "string" && sha.length > 8) {
    push("Policy hash", `${sha.slice(0, 14)}…`);
  }
  if (ev.message?.trim()) {
    push("Message", ev.message.length > 900 ? `${ev.message.slice(0, 900)}…` : ev.message);
  }
  push("Channel", ev.channel);
  push("Channel user id", ev.channel_user_id);
  push("Channel message id", ev.channel_message_id);
  push("Workflow", ev.workflow_id);
  push("Run", ev.run_id);
  push("Execution", ev.execution_id);

  const dedup = rows.filter((r, i, a) => a.findIndex((x) => x.k === r.k && x.v === r.v) === i);

  if (dedup.length === 0) {
    return <p className="text-[11px] text-zinc-500">No extra detail for this event.</p>;
  }

  return (
    <dl className="space-y-2 text-[11px]">
      {dedup.slice(0, 6).map((r) => (
        <div key={r.k}>
          <dt className="font-medium text-zinc-500">{r.k}</dt>
          <dd className="mt-0.5 break-words text-zinc-300">{r.v}</dd>
        </div>
      ))}
    </dl>
  );
}

function TrustEventCard({ ev }: { ev: TrustEventRow }) {
  const [open, setOpen] = useState(false);
  const title = humanActionLabel(ev.event_type);
  const dest = ev.destination?.trim() || "System action";

  return (
    <article className="rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <StatusStrip status={ev.status} />
        <ChannelOriginBadge channel={ev.channel} />
        {ev.sensitivity_level && String(ev.sensitivity_level).toLowerCase() !== "none" && (
          <span className="rounded border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] font-medium text-violet-200">
            {String(ev.sensitivity_level)}
          </span>
        )}
      </div>
      <h3 className="mt-2 text-sm font-semibold text-zinc-100">{title}</h3>
      <p className="mt-1 text-xs text-zinc-400">
        <span className="text-zinc-500">Target:</span>{" "}
        <span className="text-zinc-200 [overflow-wrap:anywhere] break-words">{dest}</span>
      </p>
      <p className="mt-1 text-[10px] text-zinc-500">{formatTimeAgo(ev.created_at)}</p>
      {(ev.workflow_id || ev.run_id || ev.execution_id) && (
        <p className="mt-1 text-[10px] text-zinc-500">
          {ev.workflow_id && (
            <>
              Workflow <span className="text-zinc-400">{ev.workflow_id}</span>
            </>
          )}
          {ev.workflow_id && (ev.run_id || ev.execution_id) ? " · " : null}
          {ev.run_id && (
            <>
              Run <span className="text-zinc-400">{ev.run_id}</span>
            </>
          )}
          {(ev.workflow_id || ev.run_id) && ev.execution_id ? " · " : null}
          {ev.execution_id && (
            <>
              Exec <span className="text-zinc-400">{ev.execution_id}</span>
            </>
          )}
        </p>
      )}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="mt-2 flex items-center gap-1 text-[11px] font-medium text-cyan-400/90 hover:text-cyan-300"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        Why did this happen?
      </button>
      {open && (
        <div className="mt-3 border-t border-white/10 pt-3">
          <WhyPanel ev={ev} />
        </div>
      )}
    </article>
  );
}

function TrustChannelBreakdown({
  web,
  telegram,
  system,
}: {
  web: number;
  telegram: number;
  system: number;
}) {
  return (
    <div className="mb-3 flex flex-wrap gap-3 text-[11px] text-zinc-500">
      <span>
        <span className="text-zinc-400">Web</span> · {web}
      </span>
      <span>
        <span className="text-zinc-400">Telegram</span> · {telegram}
      </span>
      <span>
        <span className="text-zinc-400">System</span> · {system}
      </span>
    </div>
  );
}

function TrustSummaryBar({ summary }: { summary: TrustSummaryResponse | null }) {
  if (!summary) return null;
  const c = summary.counts;
  return (
    <div className="mb-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5">
        <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">Window</p>
        <p className="mt-0.5 text-sm text-zinc-200">{summary.window_hours}h</p>
      </div>
      <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5">
        <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">Permissions used</p>
        <p className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-100">{c.permission_uses}</p>
      </div>
      <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5">
        <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">External · allowed / blocked</p>
        <p className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-100">
          {c.network_external_send_allowed} / {c.network_external_send_blocked}
        </p>
      </div>
      <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5">
        <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">Sensitive warnings</p>
        <p className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-100">{c.sensitive_egress_warnings}</p>
      </div>
      <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5">
        <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">Host blocks</p>
        <p className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-100">{c.host_executor_blocks}</p>
      </div>
      <div className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5">
        <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">Enforcement audits</p>
        <p className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-100">{c.safety_enforcement_paths}</p>
      </div>
    </div>
  );
}

export function TrustActivityPage() {
  const [tab, setTab] = useState<FilterTab>("all");
  const [channelTab, setChannelTab] = useState<TrustChannelTab>("all");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [events, setEvents] = useState<TrustEventRow[]>([]);
  const [summary, setSummary] = useState<TrustSummaryResponse | null>(null);

  const load = useCallback(async () => {
    if (!isConfigured()) {
      setLoading(false);
      setErr(null);
      setEvents([]);
      setSummary(null);
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const [act, sum] = await Promise.all([
        fetchTrustActivity(ACTIVITY_HOURS),
        fetchTrustSummary(SUMMARY_HOURS, 24),
      ]);
      setEvents(act.events ?? []);
      setSummary(sum);
    } catch (e) {
      setErr((e as Error).message);
      setEvents([]);
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const channelBreakdown = useMemo(() => {
    let web = 0;
    let telegram = 0;
    let system = 0;
    for (const e of events) {
      const c = (e.channel ?? "").trim().toLowerCase();
      if (c === "web") web += 1;
      else if (c === "telegram") telegram += 1;
      else system += 1;
    }
    return { web, telegram, system };
  }, [events]);

  const filtered = useMemo(
    () => filterByChannel(filterEvents(events, tab), channelTab),
    [events, tab, channelTab]
  );

  const uidPreview = typeof window !== "undefined" ? readConfig().userId : "";

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col px-4 py-8 pb-16">
      <TrustPageHeader onRefresh={() => void load()} loading={loading} />

      {!isConfigured() && (
        <div className="mb-6 rounded-lg border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          <p className="font-medium">Set your user id first</p>
          <p className="mt-1 text-amber-200/80">
            Open Nexa from the main app, use the side panel <strong>Keys</strong> or login flow, then return here.
          </p>
          <Link href="/" className="mt-2 inline-block text-sm font-medium text-cyan-400 hover:underline">
            ← Back to Nexa
          </Link>
        </div>
      )}

      {isConfigured() && err && (
        <div className="mb-4 rounded-lg border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          <p>{err}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="mt-2 rounded-md bg-rose-500/20 px-3 py-1.5 text-xs text-rose-100 hover:bg-rose-500/30"
          >
            Retry
          </button>
        </div>
      )}

      {isConfigured() && !err && (
        <>
          <p className="mb-4 text-xs text-zinc-500">
            Showing activity for <span className="text-zinc-400">{uidPreview || "—"}</span> · last ~{ACTIVITY_HOURS}h
            · summary window {SUMMARY_HOURS}h
          </p>
          <TrustSummaryBar summary={summary} />
          <TrustChannelBreakdown
            web={channelBreakdown.web}
            telegram={channelBreakdown.telegram}
            system={channelBreakdown.system}
          />
          <TrustChannelFilterTabs active={channelTab} onChange={setChannelTab} />
          <TrustFilterTabs active={tab} onChange={setTab} />
          {loading && <p className="py-8 text-center text-sm text-zinc-500">Loading trust data…</p>}
          {!loading && events.length === 0 && (
            <div className="rounded-lg border border-white/10 bg-white/[0.02] px-4 py-10 text-center">
              <p className="text-sm font-medium text-zinc-300">No recent activity</p>
              <p className="mt-2 text-sm text-zinc-500">
                Nexa hasn&apos;t recorded any trust events for your account in this window yet.
              </p>
              <p className="mt-4 text-xs text-zinc-500">
                Run a chat, workflow, or permitted action — then refresh — to see activity here.
              </p>
            </div>
          )}
          {!loading && events.length > 0 && filtered.length === 0 && (
            <div className="rounded-lg border border-white/10 bg-white/[0.02] px-4 py-8 text-center">
              <p className="text-sm text-zinc-400">No events match this filter.</p>
              <p className="mt-1 text-xs text-zinc-500">Try another tab or choose All.</p>
            </div>
          )}
          {!loading && events.length > 0 && filtered.length > 0 && (
            <TrustEventList items={filtered} />
          )}
        </>
      )}
    </div>
  );
}

function TrustPageHeader({ onRefresh, loading }: { onRefresh: () => void; loading: boolean }) {
  return (
    <header className="mb-8 border-b border-white/10 pb-6">
      <Link
        href="/"
        className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-400 transition hover:text-zinc-200"
      >
        ← Back to Nexa
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-2">
            <Shield className="h-7 w-7 text-emerald-400/90" aria-hidden />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-50">Trust & activity</h1>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-zinc-400">
              What Nexa did, why it happened, and whether it was allowed — not a raw log dump.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading || !isConfigured()}
          className="rounded-lg border border-zinc-600 bg-zinc-800/80 px-3 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-700 disabled:opacity-40"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>
    </header>
  );
}

const CHANNEL_TABS: { id: TrustChannelTab; label: string }[] = [
  { id: "all", label: "All channels" },
  { id: "web", label: "Web" },
  { id: "telegram", label: "Telegram" },
  { id: "system", label: "System" },
];

function TrustChannelFilterTabs({
  active,
  onChange,
}: {
  active: TrustChannelTab;
  onChange: (t: TrustChannelTab) => void;
}) {
  return (
    <div className="mb-3 flex flex-wrap gap-1.5">
      {CHANNEL_TABS.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={`rounded-full border px-3 py-1.5 text-[11px] font-medium transition ${
            active === id
              ? "border-sky-500/35 bg-sky-500/12 text-sky-100"
              : "border-white/10 bg-white/[0.03] text-zinc-400 hover:border-white/20 hover:text-zinc-200"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function TrustFilterTabs({
  active,
  onChange,
}: {
  active: FilterTab;
  onChange: (t: FilterTab) => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap gap-1.5">
      {TABS.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          onClick={() => onChange(id)}
          className={`rounded-full border px-3 py-1.5 text-[11px] font-medium transition ${
            active === id
              ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-100"
              : "border-white/10 bg-white/[0.03] text-zinc-400 hover:border-white/20 hover:text-zinc-200"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function TrustEventList({ items }: { items: TrustEventRow[] }) {
  return (
    <ol className="space-y-3">
      {items.map((ev) => (
        <li key={ev.id}>
          <TrustEventCard ev={ev} />
        </li>
      ))}
    </ol>
  );
}
