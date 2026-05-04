"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  Suspense,
  type KeyboardEvent,
} from "react";
import {
  ChevronDown,
  ChevronRight,
  Copy,
  LayoutDashboard,
  ListTodo,
  Loader2,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Plus,
  PanelRightClose,
  PanelRight,
  RefreshCw,
  Settings2,
  Shield,
  Sparkles,
  Trash2,
} from "lucide-react";
import { ConnectionErrorRecovery } from "@/components/connection/ConnectionErrorRecovery";
import { webDownloadBlob, webFetch, downloadBlobToFile } from "@/lib/api";
import { useConnectionDiagnosis } from "@/lib/connection/useConnectionDiagnosis";
import { DEFAULT_API_BASE, isConfigured, readConfig } from "@/lib/config";
import type {
  ChannelsStatusResponse,
  CustomAgentsListOut,
  DecisionSummary,
  LlmUsageRecent,
  LlmUsageRecentResponse,
  LlmUsageSummary,
  MemoryState,
  NexaJob,
  SessionUsageSummary,
  SystemIndicator,
  WebChatRes,
  WebHostExecutorPanel,
  WebMe,
  WebResponseSource,
  WebReleaseLatest,
  WebSessionRow,
  WebWorkContext,
} from "@/lib/nexa-types";
import type { PermissionRequiredPayload } from "@/lib/nexa-types";
import { getInputSuggestions } from "@/lib/suggestions";
import { deriveSessionTitleFromMessage } from "@/lib/sessionTitle";
import { JobInlineCard } from "./JobInlineCard";
import { ChannelAdminPanel } from "./ChannelAdminPanel";
import { GovernancePanel } from "./GovernancePanel";

type UIMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  /** Muted system event row (tool/job/document line); not a chat “bubble” */
  system_kind?: string | null;
  content: string;
  agent_key?: string | null;
  intent?: string | null;
  related_jobs?: NexaJob[];
  response_kind?: string | null;
  sources?: WebResponseSource[]; // public_web | browser_preview | web_search | marketing_web_analysis
  web_tool_line?: string | null;
  /** Server-built line; hidden when “Show cost details” is off */
  usage_subline?: string | null;
  decision?: DecisionSummary | null;
  /** Shown after a successful export from this message */
  exportInfo?: { format: string; docId: number; path: string } | null;
  permissionRequired?: PermissionRequiredPayload | null;
};

type WebDocListItem = {
  id: number;
  title: string;
  format: string;
  download_url: string;
  source_type: string;
  created_at: string;
  metadata: Record<string, unknown>;
};

type WebAccessPermissionRow = {
  id: number;
  scope: string;
  target: string;
  risk_level: string;
  status: string;
  expires_at: string | null;
  created_at: string | null;
  last_used_at?: string | null;
  reason?: string | null;
  grant_mode?: string;
};

function formatPermissionLastUsed(iso: string | null | undefined): string {
  if (!iso) return "never";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const sec = Math.round((Date.now() - t) / 1000);
  if (sec < 45) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.round(min / 60);
  if (hr < 48) return `${hr}h ago`;
  return new Date(iso).toLocaleString();
}

function riskBadgeClasses(risk: string): string {
  const r = (risk || "").toLowerCase();
  if (r === "critical" || r === "high") {
    return "border-rose-500/40 bg-rose-500/20 text-rose-100";
  }
  if (r === "medium") {
    return "border-amber-500/35 bg-amber-500/15 text-amber-100";
  }
  return "border-emerald-500/30 bg-emerald-500/15 text-emerald-100/95";
}

type WebWorkspaceRootRow = {
  id: number;
  path_normalized: string;
  label: string | null;
  is_active: boolean;
  created_at: string | null;
};

type WebNexaWorkspaceProjectRow = {
  id: number;
  name: string;
  path_normalized: string;
  description: string | null;
  created_at: string | null;
};

function id() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/** Registrable-style host for Web UI (Marketing · source line), without leading www. */
function marketingPrimarySourceHost(sources: WebResponseSource[] | undefined): string {
  const u = sources?.[0]?.url;
  if (!u) return "";
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

const LS_SHOW_COST = "nexaShowUsageDetails";
const LS_RIGHT_OPEN = "nexaRightPanelOpen";
const LS_RIGHT_W = "nexaRightPanelWidth";
const LS_COMMAND_HINTS_OPEN = "nexaCommandHintsOpen";
const LS_SESSIONS_PANEL = "nexaSessionsPanelOpen";
const LS_ACTIVE_SESSION = "nexaActiveSessionId";
const LS_SEEN_RELEASE_ID = "nexaSeenReleaseId";
const RIGHT_PANEL_W_MIN = 280;
const RIGHT_PANEL_W_MAX = 600;
const RIGHT_PANEL_W_DEFAULT = 352;

/** User message bubble: keep prompts narrower than the workspace */
const CHAT_USER_BUBBLE = "w-full max-w-[80%]";
/** Composer / chips / hints: same horizontal band as before (not full workspace width) */
const CHAT_COMPOSER_MAX = "w-full max-w-[92%] xl:max-w-[88%] 2xl:max-w-[80%]";
/** Assistant main text bubble: near-full readable width, no % max-w chain (plain text / light markdown) */
const CHAT_ASSISTANT_BUBBLE =
  "w-[96%] max-w-none overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] px-3.5 py-2.5 text-sm text-zinc-200";
const CHAT_ASSISTANT_BODY =
  "min-w-0 max-w-full [overflow-wrap:anywhere] break-words whitespace-pre-wrap text-sm leading-[1.7] text-inherit";

function formatSessionUsageLine(s: SessionUsageSummary): string {
  const cost = s.total_cost_usd;
  const c = cost != null && Number(cost) > 0 ? `$${Number(cost).toFixed(3)}` : "—";
  return `${c} · ${s.call_count} call${s.call_count === 1 ? "" : "s"} · ${(s.total_tokens || 0).toLocaleString()} tok`;
}

function formatSessionListTime(iso: string | null | undefined): string {
  if (!iso) {
    return "";
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return "";
  }
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Short date for session row meta (local calendar day). */
function formatSessionMetaDate(iso: string | null | undefined): string {
  if (!iso) {
    return "—";
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return "—";
  }
  return d.toLocaleString(undefined, { month: "short", day: "numeric" });
}

type SessionNavGroup = "today" | "yesterday" | "earlier";

function sessionRecencyBucket(iso: string | null | undefined): SessionNavGroup {
  if (!iso) {
    return "earlier";
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return "earlier";
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const day = new Date(d);
  day.setHours(0, 0, 0, 0);
  const diffDays = Math.round((today.getTime() - day.getTime()) / 864e5);
  if (diffDays === 0) {
    return "today";
  }
  if (diffDays === 1) {
    return "yesterday";
  }
  return "earlier";
}

const SESSION_GROUP_ORDER: { key: SessionNavGroup; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "yesterday", label: "Yesterday" },
  { key: "earlier", label: "Earlier" },
];

function groupSessionsForNav(
  rows: WebSessionRow[],
): { key: SessionNavGroup; label: string; items: WebSessionRow[] }[] {
  const map: Record<SessionNavGroup, WebSessionRow[]> = {
    today: [],
    yesterday: [],
    earlier: [],
  };
  for (const s of rows) {
    map[sessionRecencyBucket(s.updated_at)].push(s);
  }
  return SESSION_GROUP_ORDER.filter((g) => map[g.key].length > 0).map((g) => ({
    key: g.key,
    label: g.label,
    items: map[g.key],
  }));
}

function decisionCollapsedLine(d: DecisionSummary): string {
  const a = d.agent || "nexa";
  const t = (d.tool || "—").replace(/_/g, " ");
  return `${a} · ${t} · ${(d.risk || "low").toLowerCase()} risk`;
}

/** Composer hints — Phase 26: no legacy Nexa slash list; click fills the composer. */
const SLASH_HINTS: { cmd: string; help: string; fill: string }[] = [
  { cmd: "run mission", help: "structured multi-step mission", fill: "Mission: \n\nDeveloper: " },
  { cmd: "create agent", help: "describe a new user agent", fill: "create agent " },
  { cmd: "run dev task", help: "dev runtime (needs a registered workspace)", fill: "run dev: " },
  { cmd: "schedule task", help: "recurring or cron work", fill: "schedule task " },
  { cmd: "show memory", help: "what Nexa remembers", fill: "show memory" },
  { cmd: "show system status", help: "host health and channels", fill: "show system status" },
];

const RESEARCH_URL_CHIP = { fill: "Summarize https://", help: "read a public page (read-only)" };
const BROWSER_PREVIEW_CHIP = { fill: "Browser preview https://", help: "owner · headless browser (if enabled on host)" };
const WEB_SEARCH_CHIP = { fill: "Search the web for ", help: "optional tool search (if enabled on host)" };

/** Phase 1+ public web — same server path as Telegram; no new tab. */
const PUBLIC_URL_CHIPS: { fill: string; help: string }[] = [
  { fill: "Summarize https://", help: "visible text (read-only)" },
  { fill: "Check https:// and tell me what is on the page", help: "normal chat + URL" },
  { fill: "Compare ", help: "compare sources (uses web search when enabled)" },
];

const NEEDS_ACTION_STATUSES = new Set([
  "needs_approval",
  "needs_risk_approval",
  "waiting_approval",
  "needs_commit_approval",
  "changes_requested",
  "approved_to_commit",
]);

const ACTIVE_STATUSES = new Set(["running", "queued"]);
const KEY_PROVIDERS = ["openai", "anthropic"] as const;

function agentLabel(ak: string | null | undefined) {
  const k = (ak || "nexa").toLowerCase();
  if (k === "nexa") return "Nexa";
  /** Legacy router personas collapse to Nexa in labels (no separate persona chips). */
  if (
    ["developer", "dev", "dev_executor", "ops", "strategy", "marketing", "research", "reset", "qa"].includes(
      k,
    )
  ) {
    return "Nexa";
  }
  const raw = (ak || "nexa").replace(/^@+/, "");
  return raw ? `@${raw}` : "Nexa";
}

const PROJECT_PLACEHOLDER = "default";

type RightTab = "job" | "memory" | "system" | "keys" | "usage" | "docs";

function LoadingShell() {
  return (
    <div className="flex h-[calc(100vh-0px)] min-h-[480px] w-full max-w-[1920px] items-center justify-center bg-zinc-950 text-zinc-500">
      <div className="flex flex-col items-center gap-3">
        <span className="h-2 w-2 animate-pulse rounded-full bg-zinc-500" />
        <p className="text-xs">Loading…</p>
      </div>
    </div>
  );
}

function JobRowMini({ job, onPick }: { job: NexaJob; onPick: (id: number) => void }) {
  const st = (job.risk_level || "—") as string;
  const meta = (job.payload_json?.execution_decision || {}) as { tool_key?: string; mode?: string };
  return (
    <button
      type="button"
      onClick={() => onPick(job.id)}
      className="w-full rounded border border-white/5 px-2 py-1.5 text-left text-[11px] text-zinc-200 hover:border-white/15"
    >
      <span className="font-mono text-zinc-500">#{job.id}</span> {job.status} <span className="text-zinc-500">· {st} risk</span> · {meta.tool_key || "—"} / {meta.mode || "—"}
      <br />
      <span className="line-clamp-1 text-zinc-300">{job.title}</span>
    </button>
  );
}

function UnconfiguredPrompt() {
  return (
    <div className="flex min-h-[calc(100vh-0px)] w-full max-w-[1920px] flex-1 flex-col items-center justify-center gap-4 bg-zinc-950 p-8 text-center text-sm text-zinc-300">
      <p className="text-zinc-100">Connect Nexa</p>
      <p className="max-w-md text-zinc-500">
        Enter the API base URL and your user id. Optional: bearer token if the API uses <code className="text-zinc-400">NEXA_WEB_API_TOKEN</code>.
      </p>
      <Link className="rounded-lg bg-white/10 px-4 py-2 text-sm text-white hover:bg-white/15" href="/login">
        Open connection settings
      </Link>
    </div>
  );
}

/**
 * All hooks live here so the auth gate in `Inner` can stay minimal (avoids SSR/CSR + localStorage mismatch).
 */
function WorkspaceBody() {
  const sp = useSearchParams();

  const [rightOpen, setRightOpen] = useState(true);
  const [rightPanelWidth, setRightPanelWidth] = useState(RIGHT_PANEL_W_DEFAULT);
  const [rightTab, setRightTab] = useState<RightTab>("system");
  const resizeStartRef = useRef<{ x: number; w: number } | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      const o = localStorage.getItem(LS_RIGHT_OPEN);
      if (o === "true" || o === "false") {
        setRightOpen(o === "true");
      }
      const w = localStorage.getItem(LS_RIGHT_W);
      if (w) {
        const n = parseInt(w, 10);
        if (!Number.isNaN(n)) {
          setRightPanelWidth(Math.min(RIGHT_PANEL_W_MAX, Math.max(RIGHT_PANEL_W_MIN, n)));
        }
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      localStorage.setItem(LS_RIGHT_OPEN, rightOpen ? "true" : "false");
    } catch {
      /* ignore */
    }
  }, [rightOpen]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      localStorage.setItem(LS_RIGHT_W, String(rightPanelWidth));
    } catch {
      /* ignore */
    }
  }, [rightPanelWidth]);

  const [commandHintsOpen, setCommandHintsOpen] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      const h = localStorage.getItem(LS_COMMAND_HINTS_OPEN);
      if (h === "true" || h === "false") {
        setCommandHintsOpen(h === "true");
      }
    } catch {
      /* ignore */
    }
  }, []);
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      localStorage.setItem(LS_COMMAND_HINTS_OPEN, commandHintsOpen ? "true" : "false");
    } catch {
      /* ignore */
    }
  }, [commandHintsOpen]);

  const [composerAgentChips, setComposerAgentChips] = useState<
    { id: string; insert: string; label: string }[]
  >([{ id: "nexa", insert: "@nexa ", label: "@nexa" }]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const uid = readConfig().userId;
    if (!uid) {
      return;
    }
    void (async () => {
      try {
        const out = await webFetch<CustomAgentsListOut>("/custom-agents");
        const rows = out.agents ?? [];
        setComposerAgentChips([
          { id: "nexa", insert: "@nexa ", label: "@nexa" },
          ...rows.map((a) => {
            const h = (a.handle || "").replace(/^@/, "");
            return { id: `agent-${h}`, insert: `@${h} `, label: `@${h}` };
          }),
        ]);
      } catch {
        setComposerAgentChips([{ id: "nexa", insert: "@nexa ", label: "@nexa" }]);
      }
    })();
  }, []);

  useEffect(() => {
    const p = sp.get("p");
    if (p === "memory" || p === "system" || p === "keys" || p === "job" || p === "usage" || p === "docs") {
      setRightTab(p);
    }
  }, [sp]);

  const [sessions, setSessions] = useState<WebSessionRow[] | null>(null);
  const [sessionMenuOpenId, setSessionMenuOpenId] = useState<string | null>(null);
  const [sessionsPanelOpen, setSessionsPanelOpen] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState("default");
  const [messages, setMessages] = useState<UIMessage[]>([]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      if (localStorage.getItem(LS_SESSIONS_PANEL) === "true") {
        setSessionsPanelOpen(true);
      }
    } catch {
      /* ignore */
    }
  }, []);
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      localStorage.setItem(LS_SESSIONS_PANEL, sessionsPanelOpen ? "true" : "false");
    } catch {
      /* ignore */
    }
  }, [sessionsPanelOpen]);
  const [input, setInput] = useState("");
  /** Mission Control "Describe" links with `/?draft=…` prefill the composer. */
  useEffect(() => {
    const raw = sp.get("draft");
    if (!raw?.trim()) return;
    const text = decodeURIComponent(raw.replace(/\+/g, " ")).trim();
    if (text) setInput(text);
    if (typeof window !== "undefined") {
      const u = new URL(window.location.href);
      if (u.searchParams.has("draft")) {
        u.searchParams.delete("draft");
        const q = u.searchParams.toString();
        window.history.replaceState({}, "", u.pathname + (q ? `?${q}` : "") + u.hash);
      }
    }
  }, [sp]);
  const [suggest, setSuggest] = useState<string[]>([]);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState("");

  const [ctxProject] = useState(PROJECT_PLACEHOLDER);
  const [ctxMode] = useState<"autonomous" | "handoff">("autonomous");

  const [mem, setMem] = useState<MemoryState | null>(null);
  const [memTried, setMemTried] = useState(false);
  const [memErr, setMemErr] = useState<string | null>(null);
  const [sysInd, setSysInd] = useState<SystemIndicator[] | null>(null);
  const [hostExecutor, setHostExecutor] = useState<WebHostExecutorPanel | null>(null);
  const [systemErr, setSystemErr] = useState<string | null>(null);
  const [channelsData, setChannelsData] = useState<ChannelsStatusResponse | null>(null);
  const [channelsErr, setChannelsErr] = useState<string | null>(null);
  const [doctor, setDoctor] = useState<string | null>(null);
  const [doctorErr, setDoctorErr] = useState<string | null>(null);
  const [doctorLoading, setDoctorLoading] = useState(false);
  const [keys, setKeys] = useState<{ provider: string; has_key: boolean; last4: string }[] | null>(null);
  const [keysTried, setKeysTried] = useState(false);
  const [keysErr, setKeysErr] = useState<string | null>(null);
  const [dataError, setDataError] = useState<string | null>(null);
  const connectionDiagnosis = useConnectionDiagnosis(dataError);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [systemRefreshing, setSystemRefreshing] = useState(false);
  const [releaseLatest, setReleaseLatest] = useState<WebReleaseLatest | null>(null);
  const [releaseErr, setReleaseErr] = useState<string | null>(null);
  const [releaseLoad, setReleaseLoad] = useState(false);
  const [accessPerms, setAccessPerms] = useState<WebAccessPermissionRow[] | null>(null);
  const [accessRoots, setAccessRoots] = useState<WebWorkspaceRootRow[] | null>(null);
  const [nexaWsProjects, setNexaWsProjects] = useState<WebNexaWorkspaceProjectRow[] | null>(null);
  const [nexaWsBusyId, setNexaWsBusyId] = useState<number | null>(null);
  const [accessPanelErr, setAccessPanelErr] = useState<string | null>(null);
  const [permBusyId, setPermBusyId] = useState<number | null>(null);
  const permissionsDisplayGroups = useMemo(() => {
    if (!accessPerms?.length) {
      return [] as { scope: string; rows: WebAccessPermissionRow[] }[];
    }
    const active = accessPerms.filter((p) => p.status === "granted" || p.status === "pending");
    const sorted = [...active].sort((a, b) => b.id - a.id);
    const limited = sorted.slice(0, 14);
    const m = new Map<string, WebAccessPermissionRow[]>();
    for (const p of limited) {
      const arr = m.get(p.scope) ?? [];
      arr.push(p);
      m.set(p.scope, arr);
    }
    return Array.from(m.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([scope, rows]) => ({ scope, rows }));
  }, [accessPerms]);
  const activePermissionCount = useMemo(() => {
    if (!accessPerms?.length) return 0;
    return accessPerms.filter((p) => p.status === "granted" || p.status === "pending").length;
  }, [accessPerms]);
  const [showReleaseBanner, setShowReleaseBanner] = useState(false);
  const [releaseBannerExpanded, setReleaseBannerExpanded] = useState(false);
  const [jobPanelList, setJobPanelList] = useState<NexaJob[] | null>(null);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [keyDraft, setKeyDraft] = useState<"" | (typeof KEY_PROVIDERS)[number]>("");
  const [keyInput, setKeyInput] = useState("");

  const [usage, setUsage] = useState<LlmUsageSummary | null>(null);
  const [usageRecent, setUsageRecent] = useState<LlmUsageRecent[] | null>(null);
  const [usageErr, setUsageErr] = useState<string | null>(null);
  const [usageLoad, setUsageLoad] = useState(false);
  const [webMe, setWebMe] = useState<WebMe | null>(null);
  const [sessionUsage, setSessionUsage] = useState<SessionUsageSummary | null>(null);
  const [costDetailOn, setCostDetailOn] = useState(true);
  const [keyBusy, setKeyBusy] = useState<string | null>(null);
  const [sendingActivity, setSendingActivity] = useState("Nexa is thinking…");
  const [exportingMessageId, setExportingMessageId] = useState<string | null>(null);
  const [permissionBusyId, setPermissionBusyId] = useState<string | null>(null);
  const [docList, setDocList] = useState<WebDocListItem[] | null>(null);
  const [docErr, setDocErr] = useState<string | null>(null);
  const [docLoad, setDocLoad] = useState(false);
  const [workContext, setWorkContext] = useState<WebWorkContext | null>(null);
  const lastEffToastAt = useRef(0);

  const [jobById, setJobById] = useState<Record<number, NexaJob>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const [focusJobId, setFocusJobId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const mergeJob = useCallback((j: NexaJob) => {
    setJobById((prev) => ({ ...prev, [j.id]: { ...prev[j.id], ...j } }));
  }, []);

  const pollWebJobUntilTerminal = useCallback(
    async (jobId: number): Promise<NexaJob | null> => {
      const maxAttempts = 50;
      for (let a = 0; a < maxAttempts; a++) {
        const j = await webFetch<NexaJob>(`/web/jobs/${jobId}`);
        mergeJob(j);
        const st = (j.status || "").toLowerCase();
        if (
          st === "completed" ||
          st === "failed" ||
          st === "cancelled" ||
          st === "rejected" ||
          st === "error" ||
          st === "blocked"
        ) {
          return j;
        }
        const delayMs = 750 + Math.floor(Math.random() * 750);
        await new Promise((r) => setTimeout(r, delayMs));
      }
      return null;
    },
    [mergeJob],
  );

  const showToast = useCallback((msg: string) => {
    if (toastTimer.current) {
      clearTimeout(toastTimer.current);
    }
    setToast(msg);
    toastTimer.current = setTimeout(() => {
      setToast(null);
      toastTimer.current = null;
    }, 3500);
  }, []);

  const approvePermissionRequest = useCallback(
    async (permId: string, mode: "once" | "session") => {
      setPermissionBusyId(permId);
      try {
        const res = await webFetch<{
          reply: string;
          related_jobs: NexaJob[];
          host_job_id?: number | null;
          job_status?: string | null;
        }>(`/permissions/requests/${encodeURIComponent(permId)}/approve`, {
          method: "POST",
          body: JSON.stringify({
            grant_mode: mode,
            grant_session_hours: 8,
            session_id: activeSessionId || "default",
          }),
        });
        showToast("Permission granted — running host action…");
        for (const j of res.related_jobs ?? []) {
          mergeJob(j);
        }
        const hostJid = res.host_job_id ?? res.related_jobs?.[0]?.id ?? null;
        const ack =
          (res.reply || "").trim() || "Permission granted. Running now.";
        if (hostJid == null) {
          setMessages((prev) => [
            ...prev,
            {
              id: id(),
              role: "assistant",
              content: ack,
              related_jobs: res.related_jobs ?? [],
            },
          ]);
          return;
        }
        void (async () => {
          let head = res.related_jobs?.find((x) => x.id === hostJid);
          if (!head) {
            try {
              head = await webFetch<NexaJob>(`/web/jobs/${hostJid}`);
              mergeJob(head);
            } catch {
              setMessages((prev) => [
                ...prev,
                {
                  id: id(),
                  role: "assistant",
                  content: ack,
                  related_jobs: res.related_jobs ?? [],
                },
              ]);
              return;
            }
          }
          setFocusJobId(hostJid);
          setRightTab("job");
          setRightOpen(true);
          const st0 = (head.status || "").toLowerCase();
          const terminal =
            st0 === "completed" ||
            st0 === "failed" ||
            st0 === "cancelled" ||
            st0 === "rejected" ||
            st0 === "error" ||
            st0 === "blocked";
          const fmtResult = (j: NexaJob): string => {
            const st = (j.status || "").toLowerCase();
            if (st === "completed") {
              return (
                (j.result || "").trim() ||
                `${j.title || "Host action"} completed.`
              );
            }
            const err = (j.error_message || "").trim();
            return `${j.title || "Host action"} — ${j.status}.${err ? `\n\n${err}` : ""}`;
          };
          if (terminal) {
            setMessages((prev) => [
              ...prev,
              {
                id: id(),
                role: "assistant",
                content: fmtResult(head),
                related_jobs: [head],
              },
            ]);
            return;
          }
          setMessages((prev) => [
            ...prev,
            {
              id: id(),
              role: "assistant",
              content: ack,
              related_jobs: res.related_jobs ?? [],
            },
          ]);
          const final = await pollWebJobUntilTerminal(hostJid);
          if (!final) {
            setMessages((prev) => [
              ...prev,
              {
                id: id(),
                role: "assistant",
                content: `Still running. Check the Jobs tab for job #${hostJid}.`,
              },
            ]);
            return;
          }
          setMessages((prev) => [
            ...prev,
            {
              id: id(),
              role: "assistant",
              content: fmtResult(final),
              related_jobs: [final],
            },
          ]);
        })();
      } catch (e) {
        showToast((e as Error).message || "Could not approve");
      } finally {
        setPermissionBusyId(null);
      }
    },
    [activeSessionId, mergeJob, pollWebJobUntilTerminal, showToast],
  );

  const denyPermissionRequest = useCallback(
    async (permId: string) => {
      setPermissionBusyId(permId);
      try {
        await webFetch(`/permissions/requests/${encodeURIComponent(permId)}/deny`, {
          method: "POST",
        });
        showToast("Permission denied.");
        setMessages((prev) => [
          ...prev,
          {
            id: id(),
            role: "assistant",
            content: "Denied. I did not access that path.",
          },
        ]);
      } catch (e) {
        showToast((e as Error).message || "Could not deny");
      } finally {
        setPermissionBusyId(null);
      }
    },
    [showToast],
  );

  const loadDocList = useCallback(async () => {
    if (!isConfigured()) {
      return;
    }
    setDocLoad(true);
    setDocErr(null);
    try {
      const rows = await webFetch<WebDocListItem[]>(`/web/documents?limit=30`);
      setDocList(rows);
    } catch (e) {
      setDocErr((e as Error).message);
      setDocList([]);
    } finally {
      setDocLoad(false);
    }
  }, []);

  const loadWorkContext = useCallback(async (sessionId: string) => {
    if (!isConfigured()) {
      return;
    }
    try {
      const w = await webFetch<WebWorkContext>(
        `/web/work-context?session_id=${encodeURIComponent(sessionId)}`,
      );
      setWorkContext(w);
    } catch {
      setWorkContext(null);
    }
  }, []);

  const exportAssistantMessage = useCallback(
    async (m: UIMessage, format: "pdf" | "docx" | "md" | "txt") => {
      if (m.role !== "assistant" || !m.content?.trim()) {
        showToast("Nothing to export");
        return;
      }
      setExportingMessageId(m.id);
      try {
        const res = await webFetch<{
          id: number;
          title: string;
          format: string;
          download_url: string;
        }>("/web/documents/generate", {
          method: "POST",
          body: JSON.stringify({
            title: "",
            format,
            body_markdown: m.content,
            source_type: "chat",
            source_ref: m.id,
          }),
        });
        const blob = await webDownloadBlob(res.download_url);
        const ext =
          res.format === "docx" ? "docx" : res.format === "pdf" ? "pdf" : res.format === "md" ? "md" : "txt";
        const stem = (res.title || "nexa-export")
          .replace(/[^a-zA-Z0-9._-]+/g, "-")
          .replace(/-+/g, "-")
          .slice(0, 64);
        downloadBlobToFile(blob, `${stem || "nexa"}-${res.id}.${ext}`);
        setMessages((prev) => {
          const upd = prev.map((x) =>
            x.id === m.id
              ? { ...x, exportInfo: { format: res.format, docId: res.id, path: res.download_url } }
              : x,
          );
          return [
            ...upd,
            {
              id: id(),
              role: "system" as const,
              system_kind: "artifact",
              content: `${String(res.format).toUpperCase()} created · use Download on that message or the Docs tab`,
            },
          ];
        });
        showToast("Document created");
        void loadDocList();
        void loadWorkContext(activeSessionId);
      } catch (e) {
        setErr((e as Error).message);
        showToast("Could not create document");
      } finally {
        setExportingMessageId(null);
      }
    },
    [loadDocList, loadWorkContext, setErr, showToast, activeSessionId],
  );

  const refreshSessionUsage = useCallback(async (sessionId: string) => {
    if (!isConfigured()) {
      return;
    }
    try {
      const su = await webFetch<SessionUsageSummary>(`/web/usage/session/${encodeURIComponent(sessionId)}`);
      setSessionUsage(su);
    } catch {
      setSessionUsage(null);
    }
  }, []);

  const refreshSessionsList = useCallback(async () => {
    if (!isConfigured()) {
      return;
    }
    try {
      const s = await webFetch<WebSessionRow[]>(`/web/sessions`);
      setSessions(s);
    } catch {
      /* keep prior */
    }
  }, []);

  const loadAccessPanel = useCallback(async () => {
    if (!isConfigured()) {
      return;
    }
    setAccessPanelErr(null);
    try {
      const [perms, roots, nxProj] = await Promise.all([
        webFetch<WebAccessPermissionRow[]>(`/web/access/permissions`),
        webFetch<WebWorkspaceRootRow[]>(`/web/workspace/roots`),
        webFetch<WebNexaWorkspaceProjectRow[]>(`/web/workspace/nexa-projects`),
      ]);
      setAccessPerms(perms);
      setAccessRoots(roots);
      setNexaWsProjects(nxProj);
    } catch (e) {
      setAccessPanelErr((e as Error).message);
    }
  }, []);

  const revokePermissionRow = useCallback(
    async (pid: number) => {
      setPermBusyId(pid);
      setAccessPanelErr(null);
      try {
        await webFetch<WebAccessPermissionRow>(`/web/access/permissions/${pid}/revoke`, {
          method: "POST",
        });
        showToast(`Revoked permission #${pid}`);
        await loadAccessPanel();
      } catch (e) {
        setAccessPanelErr((e as Error).message);
      } finally {
        setPermBusyId(null);
      }
    },
    [loadAccessPanel, showToast],
  );

  const activateNexaWorkspaceProject = useCallback(
    async (projectId: number | null) => {
      if (!isConfigured()) {
        return;
      }
      setNexaWsBusyId(projectId ?? -1);
      setAccessPanelErr(null);
      try {
        await webFetch(`/web/workspace/active-project`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: projectId,
            session_id: activeSessionId || "default",
          }),
        });
        showToast(projectId ? "Active workspace project set for this chat" : "Cleared active project");
        await loadWorkContext(activeSessionId || "default");
      } catch (e) {
        setAccessPanelErr((e as Error).message);
      } finally {
        setNexaWsBusyId(null);
      }
    },
    [activeSessionId, loadWorkContext, showToast],
  );

  const loadInitialData = useCallback(async () => {
    if (!isConfigured()) {
      return;
    }
    setDataError(null);
    try {
      const me = await webFetch<WebMe>("/web/me");
      setWebMe(me);
      if (typeof window !== "undefined") {
        const k = localStorage.getItem(LS_SHOW_COST);
        if (k === "true") {
          setCostDetailOn(true);
        } else if (k === "false") {
          setCostDetailOn(false);
        } else {
          setCostDetailOn(me.is_owner && me.show_cost_details_default);
        }
      } else {
        setCostDetailOn(me.is_owner && me.show_cost_details_default);
      }
      const s = await webFetch<WebSessionRow[]>(`/web/sessions`);
      setSessions(s);
      let aid = "default";
      if (typeof window !== "undefined") {
        const st = localStorage.getItem(LS_ACTIVE_SESSION);
        if (st && s.some((x) => x.id === st)) {
          aid = st;
        }
      }
      setActiveSessionId(aid);
      await refreshSessionUsage(aid);
      const [raw, jobs] = await Promise.all([
        webFetch<{ role: string; content: string }[]>(`/web/sessions/${encodeURIComponent(aid)}/messages`),
        webFetch<NexaJob[]>(`/web/jobs?limit=20`),
      ]);
      setMessages(
        raw.map((m) => ({
          id: id(),
          role: m.role === "user" ? "user" : "assistant",
          content: m.content,
        })),
      );
      setJobById((prev) => {
        const n = { ...prev };
        for (const j of jobs) {
          n[j.id] = { ...n[j.id], ...j };
        }
        return n;
      });
      try {
        const st = await webFetch<{ indicators: SystemIndicator[]; host_executor?: WebHostExecutorPanel | null }>(
          "/web/system/status",
        );
        setSysInd(st.indicators);
        setHostExecutor(st.host_executor ?? null);
        setSystemErr(null);
      } catch {
        /* status optional for status bar */
      }
      try {
        const k = await webFetch<{ provider: string; has_key: boolean; last4: string }[]>(`/web/keys`);
        setKeys(k);
        setKeysErr(null);
      } catch {
        setKeys(null);
      } finally {
        setKeysTried(true);
      }
      void loadAccessPanel();
      void loadWorkContext(aid);
    } catch (e) {
      setDataError((e as Error).message);
    }
  }, [refreshSessionUsage, loadWorkContext, loadAccessPanel]);

  const switchWebSession = useCallback(
    async (sid: string, opts?: { force?: boolean }) => {
      const force = opts?.force ?? false;
      if (!force && sid === activeSessionId) {
        return;
      }
      setErr("");
      if (sid !== activeSessionId) {
        setActiveSessionId(sid);
        if (typeof window !== "undefined") {
          try {
            localStorage.setItem(LS_ACTIVE_SESSION, sid);
          } catch {
            /* ignore */
          }
        }
      }
      setMessages([]);
      try {
        const raw = await webFetch<{ role: string; content: string }[]>(
          `/web/sessions/${encodeURIComponent(sid)}/messages`,
        );
        setMessages(
          raw.map((m) => ({
            id: id(),
            role: m.role === "user" ? "user" : "assistant",
            content: m.content,
          })),
        );
      } catch (e) {
        setErr((e as Error).message);
      }
      void refreshSessionUsage(sid);
      void loadWorkContext(sid);
    },
    [activeSessionId, refreshSessionUsage, loadWorkContext],
  );

  const deleteWebSession = useCallback(
    async (s: WebSessionRow) => {
      if (!isConfigured()) {
        return;
      }
      const isMain = s.id === "default";
      const ok = window.confirm(
        isMain
          ? `Clear all messages in "${s.title}"? The main thread stays; chat history is removed.`
          : `Delete "${s.title}"? This removes the thread permanently.`,
      );
      if (!ok) {
        return;
      }
      setSessionMenuOpenId(null);
      setErr("");
      try {
        await webFetch(`/web/sessions/${encodeURIComponent(s.id)}`, { method: "DELETE" });
        const list = await webFetch<WebSessionRow[]>(`/web/sessions`);
        setSessions(list);
        if (activeSessionId === s.id) {
          if (isMain) {
            await switchWebSession("default", { force: true });
          } else {
            const next =
              list.find((x) => x.id === "default")?.id ??
              list.find((x) => x.id !== s.id)?.id ??
              "default";
            await switchWebSession(next);
          }
        }
        showToast(isMain ? "Main session history cleared" : "Thread deleted");
      } catch (e) {
        setErr((e as Error).message);
        showToast("Could not remove session");
      }
    },
    [activeSessionId, showToast, switchWebSession],
  );

  const newWebChat = useCallback(async () => {
    if (!isConfigured()) {
      return;
    }
    setErr("");
    try {
      const created = await webFetch<{ id: string; title: string }>("/web/sessions", {
        method: "POST",
        body: JSON.stringify({ title: "New chat" }),
      });
      setActiveSessionId(created.id);
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem(LS_ACTIVE_SESSION, created.id);
        } catch {
          /* ignore */
        }
      }
      setMessages([]);
      const list = await webFetch<WebSessionRow[]>(`/web/sessions`);
      setSessions(list);
      void refreshSessionUsage(created.id);
      void loadWorkContext(created.id);
    } catch (e) {
      setErr((e as Error).message);
    }
  }, [refreshSessionUsage, loadWorkContext]);

  const retryLoadData = useCallback(() => {
    void loadInitialData();
  }, [loadInitialData]);

  const loadReleaseLatest = useCallback(async () => {
    if (typeof window === "undefined" || !isConfigured()) {
      return;
    }
    setReleaseErr(null);
    setReleaseLoad(true);
    try {
      const n = await webFetch<WebReleaseLatest>("/web/release/latest");
      setReleaseLatest(n);
      const rid = (n.release_id || "").trim();
      let seen = "";
      try {
        seen = localStorage.getItem(LS_SEEN_RELEASE_ID) || "";
      } catch {
        seen = "";
      }
      const shouldShow = Boolean(rid) && rid !== seen;
      setShowReleaseBanner(shouldShow);
      if (!shouldShow) {
        setReleaseBannerExpanded(false);
      }
    } catch (e) {
      setReleaseErr((e as Error).message);
      setReleaseLatest(null);
      setShowReleaseBanner(false);
    } finally {
      setReleaseLoad(false);
    }
  }, []);

  const acknowledgeReleaseBanner = useCallback(() => {
    const rid = (releaseLatest?.release_id || "").trim();
    if (rid) {
      try {
        localStorage.setItem(LS_SEEN_RELEASE_ID, rid);
      } catch {
        /* ignore */
      }
    }
    setShowReleaseBanner(false);
    setReleaseBannerExpanded(false);
  }, [releaseLatest?.release_id]);

  const activeJobsToPoll = useMemo(() => {
    const s = new Set<number>();
    Object.values(jobById).forEach((j) => {
      if (["running", "queued", "needs_approval", "needs_risk_approval", "waiting_approval"].some((t) => j.status === t)) {
        s.add(j.id);
      }
    });
    return Array.from(s);
  }, [jobById]);

  useEffect(() => {
    if (typeof window === "undefined" || !isConfigured()) {
      return;
    }
    void loadInitialData();
  }, [loadInitialData]);

  useEffect(() => {
    if (typeof window === "undefined" || !isConfigured()) {
      return;
    }
    void loadReleaseLatest();
  }, [loadReleaseLatest]);

  useEffect(() => {
    if (typeof window === "undefined" || !isConfigured() || !rightOpen) {
      return;
    }
    if (rightTab === "memory" && !memTried) {
      setMemTried(true);
      setMemErr(null);
      webFetch<MemoryState>("/web/memory/state")
        .then((m) => {
          setMem(m);
          setMemErr(null);
        })
        .catch((e) => {
          setMem(null);
          setMemErr((e as Error).message);
        });
    }
    if (rightTab === "system") {
      setSystemErr(null);
      setChannelsErr(null);
      webFetch<{ indicators: SystemIndicator[]; host_executor?: WebHostExecutorPanel | null }>("/web/system/status")
        .then((r) => {
          setSysInd(r.indicators);
          setHostExecutor(r.host_executor ?? null);
          setSystemErr(null);
        })
        .catch((e) => {
          setSysInd(null);
          setSystemErr((e as Error).message);
        });
      webFetch<ChannelsStatusResponse>("/channels/status")
        .then((c) => {
          setChannelsData(c);
          setChannelsErr(null);
        })
        .catch((e) => {
          setChannelsData(null);
          setChannelsErr((e as Error).message);
        });
    }
    if (rightTab === "keys" && !keysTried) {
      setKeysTried(true);
      setKeysErr(null);
      webFetch<{ provider: string; has_key: boolean; last4: string }[]>(`/web/keys`)
        .then((k) => {
          setKeys(k);
          setKeysErr(null);
        })
        .catch((e) => {
          setKeys(null);
          setKeysErr((e as Error).message);
        });
    }
  }, [rightOpen, rightTab, memTried, keysTried]);

  const loadDoctor = useCallback(async () => {
    if (doctor !== null) {
      return;
    }
    setDoctorErr(null);
    setDoctorLoading(true);
    try {
      const d = await webFetch<{ text: string }>("/web/system/doctor");
      setDoctor(d.text != null ? String(d.text) : "");
      setDoctorErr(null);
    } catch (e) {
      console.error("Failed to load doctor report", e);
      setDoctorErr("Could not load full doctor report. Check API connection.");
      showToast("Could not load doctor report");
    } finally {
      setDoctorLoading(false);
    }
  }, [doctor, showToast]);

  // Poll in-flight dev jobs
  useEffect(() => {
    if (!isConfigured() || activeJobsToPoll.length === 0) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    const run = () => {
      for (const jid of activeJobsToPoll) {
        void webFetch<NexaJob>(`/web/jobs/${jid}`).then(mergeJob).catch(() => {
          /* ignore transient poll errors */
        });
      }
    };
    void run();
    pollRef.current = setInterval(run, 2500);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
    };
  }, [activeJobsToPoll, mergeJob]);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages, sending]);

  const refetchSystemStatus = useCallback(async () => {
    setSystemRefreshing(true);
    setSystemErr(null);
    setChannelsErr(null);
    try {
      const st = await webFetch<{ indicators: SystemIndicator[]; host_executor?: WebHostExecutorPanel | null }>(
        "/web/system/status",
      );
      setSysInd(st.indicators);
      setHostExecutor(st.host_executor ?? null);
    } catch (e) {
      setSysInd(null);
      setSystemErr((e as Error).message);
    }
    try {
      const ch = await webFetch<ChannelsStatusResponse>("/channels/status");
      setChannelsData(ch);
    } catch (e) {
      setChannelsData(null);
      setChannelsErr((e as Error).message);
    }
    try {
      await loadAccessPanel();
    } finally {
      setSystemRefreshing(false);
    }
    showToast("Status refreshed");
  }, [showToast, loadAccessPanel]);

  const loadUsagePanel = useCallback(async () => {
    if (!isConfigured()) return;
    setUsageLoad(true);
    setUsageErr(null);
    try {
      const s = await webFetch<LlmUsageSummary>("/web/usage/summary?period=today");
      setUsage(s);
      const r = await webFetch<LlmUsageRecentResponse>("/web/usage/recent?limit=20");
      setUsageRecent(r.items);
    } catch (e) {
      setUsageErr((e as Error).message);
      setUsage(null);
      setUsageRecent(null);
    } finally {
      setUsageLoad(false);
    }
  }, []);

  useEffect(() => {
    if (rightOpen && rightTab === "usage" && isConfigured()) {
      void loadUsagePanel();
    }
  }, [rightOpen, rightTab, loadUsagePanel]);

  useEffect(() => {
    if (rightOpen && rightTab === "docs" && isConfigured()) {
      void loadDocList();
    }
  }, [rightOpen, rightTab, loadDocList]);

  const copyDoctorReport = useCallback(() => {
    if (doctor == null || doctorErr) {
      return;
    }
    void navigator.clipboard.writeText(doctor);
    showToast("Report copied");
  }, [doctor, doctorErr, showToast]);

  useEffect(() => {
    if (typeof window === "undefined" || !isConfigured() || !rightOpen || rightTab !== "job") {
      return;
    }
    setJobPanelList(null);
    void webFetch<NexaJob[]>(`/web/jobs?limit=50`)
      .then((rows) => {
        setJobPanelList(rows);
        for (const j of rows) {
          mergeJob(j);
        }
      })
      .catch(() => {
        setJobPanelList([]);
      });
  }, [rightOpen, rightTab, mergeJob]);

  const allJobsForPanel = useMemo(() => {
    const m = new Map<number, NexaJob>();
    for (const j of Object.values(jobById)) {
      m.set(j.id, j);
    }
    if (jobPanelList) {
      for (const j of jobPanelList) {
        m.set(j.id, j);
      }
    }
    return Array.from(m.values()).sort((a, b) => b.id - a.id);
  }, [jobPanelList, jobById]);

  const jobGroups = useMemo(() => {
    const active = allJobsForPanel.filter((j) => ACTIVE_STATUSES.has(j.status));
    const need = allJobsForPanel.filter((j) => NEEDS_ACTION_STATUSES.has(j.status));
    const u = new Set([...active, ...need].map((j) => j.id));
    const hist = allJobsForPanel.filter((j) => !u.has(j.id));
    return { active, need, hist };
  }, [allJobsForPanel]);

  const lastAssistantAgent = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i]!.role === "assistant" && messages[i]!.agent_key) {
        return agentLabel(messages[i]!.agent_key);
      }
    }
    return "Nexa";
  }, [messages]);

  const headerSession = useMemo(() => {
    if (!sessions || sessions.length === 0) {
      return null;
    }
    return sessions.find((s) => s.id === activeSessionId) ?? sessions[0] ?? null;
  }, [sessions, activeSessionId]);

  const sessionNavGroups = useMemo(
    () => (sessions && sessions.length > 0 ? groupSessionsForNav(sessions) : []),
    [sessions],
  );

  const browserPreviewChip = useMemo(() => {
    const b = sysInd?.find((i) => i.id === "browser_preview");
    const on = b?.detail === "enabled";
    if (on) {
      return BROWSER_PREVIEW_CHIP;
    }
    return {
      ...BROWSER_PREVIEW_CHIP,
      help: "owner-only — off on this host (see System → Browser preview)",
    };
  }, [sysInd]);

  const webSearchChip = useMemo(() => {
    const w = sysInd?.find((i) => i.id === "web_search");
    if (!w) {
      return { ...WEB_SEARCH_CHIP, help: "see System for status" };
    }
    if (w.level === "ok" && w.detail?.startsWith("enabled:")) {
      return { ...WEB_SEARCH_CHIP, help: "Web search enabled" };
    }
    if ((w.detail || "").includes("disabled")) {
      return {
        ...WEB_SEARCH_CHIP,
        help: "Web search disabled — direct URLs and public read still work",
      };
    }
    return { ...WEB_SEARCH_CHIP, help: w.detail || WEB_SEARCH_CHIP.help };
  }, [sysInd]);

  const providerLine = useMemo(() => {
    if (!keys || !keys.length) {
      return "—";
    }
    const a = keys.find((x) => x.provider === "anthropic");
    const o = keys.find((x) => x.provider === "openai");
    const bits: string[] = [];
    if (a?.has_key) {
      bits.push("Anthropic");
    }
    if (o?.has_key) {
      bits.push("OpenAI");
    }
    if (bits.length === 0) {
      return "System / env";
    }
    return `User: ${bits.join(" · ")}`;
  }, [keys]);

  const healthOnline = useMemo(() => {
    if (dataError) {
      return "Degraded";
    }
    if (!sysInd) {
      return "…";
    }
    if (sysInd.some((i) => i.level === "error")) {
      return "Check system";
    }
    if (sysInd.some((i) => i.level === "warning")) {
      return "Degraded";
    }
    return "Online";
  }, [sysInd, dataError]);

  const statusHealthTone = useMemo((): "ok" | "warning" | "error" => {
    if (dataError) {
      return "warning";
    }
    if (!sysInd) {
      return "warning";
    }
    if (sysInd.some((i) => i.level === "error")) {
      return "error";
    }
    if (sysInd.some((i) => i.level === "warning")) {
      return "warning";
    }
    return "ok";
  }, [sysInd, dataError]);

  const { statusBadgeBox, statusBadgeText, statusDotClass } = useMemo(() => {
    if (statusHealthTone === "ok") {
      return {
        statusBadgeBox: "inline-flex max-w-full items-center gap-1.5 rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5",
        statusBadgeText: "text-[10px] font-medium text-emerald-300",
        statusDotClass: "h-2 w-2 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]",
      };
    }
    if (statusHealthTone === "error") {
      return {
        statusBadgeBox: "inline-flex max-w-full items-center gap-1.5 rounded border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5",
        statusBadgeText: "text-[10px] font-medium text-rose-300",
        statusDotClass: "h-2 w-2 shrink-0 rounded-full bg-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.55)]",
      };
    }
    return {
      statusBadgeBox: "inline-flex max-w-full items-center gap-1.5 rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5",
      statusBadgeText: "text-[10px] font-medium text-amber-300",
      statusDotClass: "h-2 w-2 shrink-0 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.55)]",
    };
  }, [statusHealthTone]);

  const filteredMemNotes = useMemo(() => {
    if (!mem?.notes) {
      return [];
    }
    const q = memoryQuery.trim().toLowerCase();
    if (!q) {
      return mem.notes;
    }
    return mem.notes.filter(
      (n) =>
        (n.key || "").toLowerCase().includes(q) ||
        (n.content || "").toLowerCase().includes(q) ||
        (n.summary || "").toLowerCase().includes(q) ||
        (n.category || "").toLowerCase().includes(q),
    );
  }, [mem, memoryQuery]);

  const saveKeyForProvider = useCallback(
    async (p: (typeof KEY_PROVIDERS)[number]) => {
      const t = keyInput.trim();
      if (!t) {
        showToast("Enter an API key");
        return;
      }
      setKeyBusy(p);
      setKeysErr(null);
      try {
        await webFetch("/web/keys", {
          method: "POST",
          body: JSON.stringify({ provider: p, key: t }),
        });
        setKeyInput("");
        setKeyDraft("");
        const k = await webFetch<{ provider: string; has_key: boolean; last4: string }[]>(`/web/keys`);
        setKeys(k);
        showToast("Key saved");
      } catch (e) {
        showToast((e as Error).message || "Could not save key");
      } finally {
        setKeyBusy(null);
      }
    },
    [keyInput, showToast],
  );

  const removeKeyForProvider = useCallback(
    async (p: string) => {
      setKeyBusy(p);
      setKeysErr(null);
      try {
        await webFetch(`/web/keys/${encodeURIComponent(p)}`, { method: "DELETE" });
        const k = await webFetch<{ provider: string; has_key: boolean; last4: string }[]>(`/web/keys`);
        setKeys(k);
        showToast("Key removed");
      } catch (e) {
        showToast((e as Error).message || "Could not remove key");
      } finally {
        setKeyBusy(null);
      }
    },
    [showToast],
  );

  const onType = (v: string) => {
    setInput(v);
    setSuggest(getInputSuggestions(v, 5));
  };

  const send = async () => {
    const t = input.trim();
    if (!t || sending) {
      return;
    }
    setInput("");
    setSuggest([]);
    setErr("");
    setMessages((m) => [...m, { id: id(), role: "user", content: t }]);
    setSending(true);
    const tl = t.toLowerCase();
    if (tl.startsWith("run dev")) {
      setSendingActivity("Running dev mission…");
    } else if (tl.includes("http://") || tl.includes("https://")) {
      setSendingActivity("Reading or fetching…");
    } else if (tl.includes("search the web") || (tl.includes("search") && tl.includes("http"))) {
      setSendingActivity("Searching web…");
    } else if (t.trim().startsWith("/")) {
      setSendingActivity("Running command…");
    } else {
      setSendingActivity("Nexa is thinking…");
    }
    try {
      const out: WebChatRes = await webFetch("/web/chat", {
        method: "POST",
        body: JSON.stringify({ message: t, session_id: activeSessionId }),
      });
      const related = out.related_jobs ?? [];
      const u = id();
      for (const j of related) {
        mergeJob(j);
      }
      if (related[0]) {
        setFocusJobId(related[0].id);
        setRightTab("job");
        setRightOpen(true);
      }
      const sev = out.system_events ?? [];
      const sysRows: UIMessage[] = sev
        .filter((e) => (e.text || "").trim())
        .map((e) => ({
          id: id(),
          role: "system" as const,
          system_kind: e.kind,
          content: (e.text || "").trim(),
        }));
      setMessages((m) => [
        ...m,
        ...sysRows,
        {
          id: u,
          role: "assistant",
          content: out.reply,
          agent_key: out.agent_key,
          intent: out.intent,
          related_jobs: related,
          response_kind: out.response_kind ?? null,
          permissionRequired: out.permission_required ?? null,
          sources: out.sources ?? [],
          web_tool_line: out.web_tool_line ?? null,
          usage_subline: out.usage_summary?.subline ?? null,
          decision: out.decision_summary ?? null,
        },
      ]);
      void refreshSessionUsage(activeSessionId);
      setSessions((prev) => {
        if (!prev) {
          return prev;
        }
        return prev.map((s) => {
          if (s.id !== activeSessionId) {
            return s;
          }
          if ((s.title || "") !== "New chat") {
            return s;
          }
          return { ...s, title: deriveSessionTitleFromMessage(t) };
        });
      });
      void refreshSessionsList();
      void loadWorkContext(activeSessionId);
      const sub = out.usage_summary?.subline;
      if (webMe?.is_owner && sub && Date.now() - lastEffToastAt.current > 45_000) {
        showToast(`Message processed · ${sub}`);
        lastEffToastAt.current = Date.now();
      } else {
        showToast("Message sent");
      }
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      const net =
        raw.includes("Failed to fetch") ||
        raw.includes("NetworkError") ||
        raw.includes("Load failed");
      const apiBase = readConfig().apiBase || DEFAULT_API_BASE;
      setErr(
        net
          ? `${raw} — Is the API up? (${apiBase}) Check browser console / Network tab.`
          : raw,
      );
    } finally {
      setSending(false);
    }
  };

  function handleComposerKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key !== "Enter") {
      return;
    }
    if (e.shiftKey) {
      return;
    }
    e.preventDefault();
    if (!input.trim() || sending) {
      return;
    }
    void send();
  }

  function deleteLocalUserMessage(messageId: string) {
    setMessages((items) => items.filter((x) => x.id !== messageId));
  }

  function editUserMessage(m: UIMessage) {
    setInput(m.content);
    setMessages((items) => items.filter((x) => x.id !== m.id));
    setSuggest([]);
    setErr("");
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  const indLevelClass = (lv: string) => {
    if (lv === "ok") {
      return "text-emerald-300";
    }
    if (lv === "error") {
      return "text-rose-300";
    }
    if (lv === "warning" || lv === "unknown") {
      return "text-amber-300";
    }
    return "text-zinc-200";
  };

  const startResizeRight = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    if (!rightOpen) {
      return;
    }
    resizeStartRef.current = { x: e.clientX, w: rightPanelWidth };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [rightOpen, rightPanelWidth]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const s = resizeStartRef.current;
      if (!s) {
        return;
      }
      const delta = e.clientX - s.x;
      const next = Math.min(
        RIGHT_PANEL_W_MAX,
        Math.max(RIGHT_PANEL_W_MIN, s.w + delta)
      );
      setRightPanelWidth(next);
    };
    const onUp = () => {
      if (resizeStartRef.current) {
        resizeStartRef.current = null;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("blur", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("blur", onUp);
    };
  }, []);

  useEffect(() => {
    if (!sessionMenuOpenId) {
      return;
    }
    const onDoc = (e: MouseEvent) => {
      const el = e.target as HTMLElement | null;
      if (el?.closest("[data-session-menu-root]")) {
        return;
      }
      setSessionMenuOpenId(null);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [sessionMenuOpenId]);

  return (
    <div className="flex h-[calc(100vh-0px)] min-h-[480px] w-full min-w-0 max-w-[1920px] items-stretch">
      <aside className="flex w-16 shrink-0 flex-col border-r border-white/10 bg-black/30 py-3">
        <div className="px-1 text-center text-[9px] font-bold uppercase tracking-tighter text-emerald-200/80">Nexa</div>
        <nav className="mt-2 flex flex-1 flex-col items-center gap-1.5">
          <button
            type="button"
            title="Chat sessions"
            aria-label="Chat sessions"
            onClick={() => {
              setSessionsPanelOpen((o) => !o);
              inputRef.current?.focus();
            }}
            className={
              sessionsPanelOpen
                ? "rounded-lg p-2.5 bg-white/10 text-white"
                : "rounded-lg p-2.5 text-zinc-400 hover:bg-white/5 hover:text-white"
            }
          >
            <MessageSquare className="h-4 w-4" />
          </button>
          <button
            type="button"
            title="Jobs"
            aria-label="Jobs"
            onClick={() => {
              setRightOpen(true);
              setRightTab("job");
            }}
            className="rounded-lg p-2.5 text-zinc-500 hover:bg-white/5 hover:text-zinc-300"
          >
            <ListTodo className="h-3.5 w-3.5" />
          </button>
          <div className="flex-1" />
          <a
            href="/login"
            className="rounded-lg p-2.5 text-zinc-500 hover:bg-white/5"
            title="Connection settings"
            aria-label="Connection settings"
          >
            <Settings2 className="h-4 w-4" />
          </a>
        </nav>
      </aside>

      {sessionsPanelOpen && (
        <aside
          className="flex w-[240px] shrink-0 flex-col border-r border-white/10 bg-zinc-950/95"
          aria-label="Work threads"
        >
          <div className="shrink-0 border-b border-white/5 px-3 pb-3 pt-2.5">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-500">SESSIONS</p>
            <p className="mt-1 text-[10px] leading-tight text-zinc-600">Work threads</p>
            <button
              type="button"
              onClick={() => void newWebChat()}
              title="New session"
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 text-sm font-medium text-zinc-100 transition-colors duration-150 hover:bg-zinc-700"
            >
              <Plus className="h-4 w-4 shrink-0 text-emerald-400/90" />
              New session
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden scroll-smooth px-2 py-2">
            {sessions && sessions.length === 0 && (
              <p className="px-2 py-6 text-center text-[11px] leading-relaxed text-zinc-500">
                No work threads yet.
              </p>
            )}
            {sessions && sessions.length > 0 && (
              <div className="space-y-4">
                {sessionNavGroups.map((grp) => (
                  <div key={grp.key}>
                    <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                      {grp.label}
                    </p>
                    <ul className="space-y-1" role="list">
                      {grp.items.map((s) => {
                        const isActive = s.id === activeSessionId;
                        const sub = s.preview || s.active_topic || s.summary || "—";
                        return (
                          <li key={s.id} className="group">
                            <div
                              className={
                                isActive
                                  ? "flex w-full items-stretch rounded-lg border-l-2 border-emerald-500 bg-zinc-800 shadow-sm ring-1 ring-white/5 transition-colors duration-150"
                                  : "flex w-full items-stretch rounded-lg border-l-2 border-transparent transition-colors duration-150 hover:bg-zinc-800/60"
                              }
                            >
                              <button
                                type="button"
                                onClick={() => {
                                  setSessionsPanelOpen(true);
                                  setSessionMenuOpenId(null);
                                  void switchWebSession(s.id);
                                }}
                                className="flex min-w-0 flex-1 gap-2.5 py-3 pl-3 pr-1 text-left"
                              >
                                <span
                                  className={
                                    isActive
                                      ? "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.45)]"
                                      : "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-600"
                                  }
                                  aria-hidden
                                />
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-sm font-semibold text-zinc-100">{s.title}</p>
                                  <p className="mt-0.5 truncate text-xs text-zinc-400">{sub}</p>
                                  <p className="mt-1.5 text-[10px] tabular-nums text-zinc-500">
                                    Messages · {s.message_count} · {formatSessionMetaDate(s.updated_at)}
                                  </p>
                                </div>
                              </button>
                              <div
                                className="relative shrink-0 pr-1.5 pt-2"
                                data-session-menu-root
                              >
                                <button
                                  type="button"
                                  aria-label="Session actions"
                                  title="More"
                                  aria-haspopup="menu"
                                  aria-expanded={sessionMenuOpenId === s.id}
                                  onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    setSessionMenuOpenId((cur) => (cur === s.id ? null : s.id));
                                  }}
                                  className={
                                    sessionMenuOpenId === s.id
                                      ? "rounded-md p-1.5 text-zinc-200 hover:bg-white/10"
                                      : "rounded-md p-1.5 text-zinc-500 opacity-70 hover:bg-white/5 hover:text-zinc-200 group-hover:opacity-100"
                                  }
                                >
                                  <MoreHorizontal className="h-4 w-4" />
                                </button>
                                {sessionMenuOpenId === s.id && (
                                  <div
                                    role="menu"
                                    className="absolute right-0 top-full z-30 mt-0.5 min-w-[9.5rem] rounded-md border border-white/10 bg-zinc-900 py-1 shadow-lg shadow-black/40"
                                  >
                                    <button
                                      type="button"
                                      role="menuitem"
                                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-zinc-100 hover:bg-white/10"
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        void deleteWebSession(s);
                                      }}
                                    >
                                      <Trash2 className="h-3.5 w-3.5 shrink-0 text-zinc-400" />
                                      {s.id === "default" ? "Clear history" : "Delete thread"}
                                    </button>
                                  </div>
                                )}
                              </div>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      )}

      <div className="flex w-full min-h-0 min-w-0 flex-1 flex-col px-6 xl:px-10">
        <header className="shrink-0 border-b border-white/10 bg-black/20 py-2.5 text-xs text-zinc-400">
          <div className="flex items-center">
            <div className="min-w-0">
              {headerSession ? (
                <>
                  <p className="truncate font-medium text-zinc-100">
                    {headerSession.title || headerSession.active_topic || "Nexa"}
                  </p>
                  <p className="text-[10px] text-zinc-500">Messages · {headerSession.message_count}</p>
                </>
              ) : (
                <p className="text-zinc-100">Nexa</p>
              )}
            </div>
            <div className="ml-auto">
              <button
                type="button"
                onClick={() => setRightOpen((o) => !o)}
                className="rounded p-1.5 text-zinc-500 hover:bg-white/5"
                title="Toggle side panel"
                aria-label="Toggle side panel"
              >
                {rightOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRight className="h-4 w-4" />}
              </button>
            </div>
          </div>
          {webMe?.is_owner && sessionUsage && (
            <p className="mt-1.5 w-full text-right text-[10px] text-zinc-500" title="This session: estimated LLM spend and tokens">
              Session · {formatSessionUsageLine(sessionUsage)}
            </p>
          )}
          <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1 border-t border-white/5 pt-2.5 text-[10px] leading-tight text-zinc-500">
            <span>
              <span className="text-zinc-600">Project</span>{" "}
              <b className="text-zinc-200">{ctxProject}</b>
            </span>
            <span className="text-zinc-600">·</span>
            <span>
              <span className="text-zinc-600">Agent</span> <b className="text-zinc-200">{lastAssistantAgent}</b>
            </span>
            <span className="text-zinc-600">·</span>
            <span>
              <span className="text-zinc-600">Mode</span>{" "}
              <b className="text-zinc-200">{ctxMode === "autonomous" ? "Auto" : "Handoff"}</b>
            </span>
            <span className="text-zinc-600">·</span>
            <span>
              <span className="text-zinc-600">Provider</span> <b className="text-zinc-200">{providerLine}</b>
            </span>
            <span className="text-zinc-600">·</span>
            <span className="inline-flex min-w-0 items-center gap-1">
              <span className="shrink-0 text-zinc-600">Status</span>
              <span
                className={statusBadgeBox}
                title={statusHealthTone === "ok" ? "Connected" : "System may need attention"}
              >
                <span className={statusDotClass} />
                <span className={statusBadgeText}>{healthOnline}</span>
              </span>
            </span>
          </div>
        </header>

        {isConfigured() && showReleaseBanner && releaseLatest && (
          <div className="shrink-0 border-b border-zinc-800 bg-zinc-900 px-6 py-2 text-sm text-zinc-300 xl:px-10">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-zinc-100">What’s new in Nexa</p>
                {releaseLatest.items && releaseLatest.items.length > 0 ? (
                  <ul className="mt-1 list-none space-y-0.5 pl-0 text-zinc-400">
                    {releaseLatest.items.slice(0, 6).map((t, idx) => (
                      <li key={idx} className="flex gap-2 [overflow-wrap:anywhere] break-words">
                        <span className="shrink-0 text-zinc-600">•</span>
                        <span>{t}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-xs text-zinc-500">See the System tab for release notes.</p>
                )}
                {releaseBannerExpanded && releaseLatest.full_text ? (
                  <pre className="mt-2 max-h-48 overflow-auto rounded border border-zinc-800 bg-black/30 p-2 text-[11px] leading-snug text-zinc-400 whitespace-pre-wrap">
                    {releaseLatest.full_text}
                  </pre>
                ) : null}
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={acknowledgeReleaseBanner}
                  className="rounded border border-zinc-600 bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-100 hover:bg-zinc-700"
                >
                  Got it
                </button>
                {releaseLatest.full_text ? (
                  <button
                    type="button"
                    onClick={() => setReleaseBannerExpanded((e) => !e)}
                    className="rounded px-2 py-1 text-xs text-zinc-400 hover:text-zinc-200"
                  >
                    {releaseBannerExpanded ? "Hide details" : "View details"}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        )}

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden py-3 md:py-4">
          {err && <p className="mb-2 text-sm text-rose-400">{err}</p>}

          {dataError ? (
            <ConnectionErrorRecovery
              dataError={dataError}
              diagnosis={connectionDiagnosis}
              onRetry={retryLoadData}
            />
          ) : null}

          {messages.length === 0 && !sending && !dataError && (
            <div className="mx-auto max-w-md py-8 text-center text-sm text-zinc-400">
              <p className="text-lg text-zinc-100">Welcome to Nexa</p>
              <p className="mt-3 text-zinc-500">Try:</p>
              <ul className="mt-2 list-none space-y-1.5 pl-0 text-left text-sm text-zinc-400">
                <li>• Ask a normal question</li>
                <li>• run dev: fix failing tests (with a dev workspace)</li>
                <li>• create agent — describe how it should behave</li>
                <li>• show memory or show system status</li>
                <li>• Open System to check health</li>
                <li>
                  •{" "}
                  <Link href="/mission-control" className="text-violet-400/90 underline-offset-2 hover:underline">
                    Mission Control
                  </Link>{" "}
                  — priorities, approvals, and active work
                </li>
                <li>
                  •{" "}
                  <Link href="/trust" className="text-emerald-400/90 underline-offset-2 hover:underline">
                    Trust & activity
                  </Link>{" "}
                  — what Nexa allowed or blocked
                </li>
                <li>• Open Keys to add your API key</li>
                <li className="text-zinc-500">
                  Custom agents: ask in chat, e.g. &quot;Create me a custom agent: financial advisor&quot; (no
                  extra UI)
                </li>
              </ul>
            </div>
          )}

          {messages.map((m) => {
            if (m.role === "system") {
              return (
                <div
                  key={m.id}
                  className="mb-2.5 w-full min-w-0 text-center text-[10px] leading-relaxed text-zinc-500"
                >
                  <span
                    className="inline-block max-w-full break-words rounded border border-white/[0.06] bg-zinc-900/40 px-2 py-0.5"
                    title={m.system_kind || "system"}
                  >
                    {m.content}
                  </span>
                </div>
              );
            }
            return (
            <div
              key={m.id}
              className={`group mb-4 min-w-0 ${
                m.role === "user"
                  ? "ml-auto flex w-full min-w-0 flex-row items-start justify-end gap-1.5"
                  : "mr-auto w-full min-w-0"
              } focus-within:ring-0`}
            >
              {m.role === "user" ? (
                <>
                  <div className={`ml-0 min-w-0 shrink ${CHAT_USER_BUBBLE}`}>
                    <div className="cursor-default overflow-hidden rounded-2xl border border-cyan-500/20 bg-cyan-500/5 px-3.5 py-2.5 text-sm leading-relaxed text-cyan-50/95">
                      <span className="whitespace-pre-wrap break-words">{m.content}</span>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-row items-center gap-0.5 self-start pt-1.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                    <button
                      type="button"
                      onClick={() => editUserMessage(m)}
                      className="rounded p-0.5 text-zinc-500 hover:bg-white/10 hover:text-cyan-200/90"
                      title="Edit"
                      aria-label="Edit message"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteLocalUserMessage(m.id)}
                      className="rounded p-0.5 text-zinc-500 hover:bg-white/10 hover:text-rose-300/90"
                      title="Delete"
                      aria-label="Delete message from view"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </>
              ) : (
                <div className="min-w-0 w-full">
                  {m.agent_key && (
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wide text-zinc-500">
                      <span className="text-zinc-200">
                        Agent: <b className="text-zinc-200">{agentLabel(m.agent_key)}</b>
                      </span>
                      {m.intent && (
                        <span>
                          · Intent: <b className="lowercase text-zinc-400">{m.intent}</b>
                        </span>
                      )}
                    </div>
                  )}
                  {((m.response_kind === "public_web" ||
                    m.response_kind === "browser_preview" ||
                    m.response_kind === "web_search" ||
                    m.response_kind === "marketing_web_analysis") &&
                    (m.response_kind === "marketing_web_analysis"
                      ? (m.web_tool_line || "").trim().length > 0 || (m.sources && m.sources.length > 0)
                      : m.sources && m.sources.length > 0)) && (
                    <div className="mb-1.5 rounded border border-violet-500/15 bg-violet-500/5 px-2.5 py-1.5 text-[10px] leading-relaxed text-zinc-400">
                      <div className="text-violet-200/90">
                        {m.response_kind === "marketing_web_analysis"
                          ? "Marketing · Web analysis"
                          : m.response_kind === "browser_preview"
                            ? "Research · Browser preview"
                            : m.response_kind === "web_search"
                              ? "Research · Web search"
                              : m.agent_key === "nexa" && m.response_kind === "public_web"
                                ? "Nexa · Public web"
                                : m.response_kind === "public_web"
                                  ? "Research · Public web"
                                  : "Sources"}
                      </div>
                      {m.response_kind === "marketing_web_analysis" && (
                        <div className="mt-0.5 text-zinc-500">Based on public web data</div>
                      )}
                      {m.response_kind === "marketing_web_analysis" && m.web_tool_line && (
                        <div className="mt-0.5 text-zinc-500">{m.web_tool_line}</div>
                      )}
                      {m.response_kind === "marketing_web_analysis" &&
                        marketingPrimarySourceHost(m.sources) && (
                          <div className="mt-0.5 text-zinc-500">
                            Source: {marketingPrimarySourceHost(m.sources)}
                          </div>
                        )}
                      {m.sources && m.sources.length > 0 && (
                        <ul className="mt-1 list-inside list-disc text-zinc-500">
                          {(m.sources || []).slice(0, 8).map((src) => (
                            <li key={src.url} className="text-[10px] text-zinc-300">
                              <span className="text-zinc-400">{(src.title || "").replace(/\s+/g, " ").slice(0, 120) || "Source"}: </span>
                              <a
                                href={src.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="font-mono text-[10px] text-cyan-300/90 underline decoration-cyan-500/30"
                              >
                                {src.url}
                              </a>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                  <div className={CHAT_ASSISTANT_BUBBLE}>
                    <div className={CHAT_ASSISTANT_BODY}>{m.content}</div>
                  </div>
                  {m.permissionRequired && (
                    <div className="mt-2 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] px-3 py-2.5">
                      <p className="text-[11px] font-medium text-amber-100/95">
                        🔐 Permission required
                      </p>
                      <p className="mt-1.5 text-[10px] uppercase tracking-wide text-zinc-500">
                        {(m.permissionRequired.scope || "").toLowerCase() === "file_write"
                          ? "Nexa wants to write:"
                          : "Nexa wants to read:"}
                      </p>
                      <p className="mt-0.5 font-mono text-[11px] leading-snug text-zinc-100 [overflow-wrap:anywhere]">
                        {m.permissionRequired.target}
                      </p>
                      <p className="mt-2 text-[10px] text-zinc-400">
                        <span className="text-zinc-500">Reason: </span>
                        {m.permissionRequired.reason}
                      </p>
                      <p className="mt-1 text-[10px] text-zinc-400">
                        <span className="text-zinc-500">Risk: </span>
                        {(m.permissionRequired.risk_level || "").replace(/^./, (x) =>
                          x.toUpperCase(),
                        )}{" "}
                        — local access
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={
                            permissionBusyId === m.permissionRequired.permission_request_id
                          }
                          className="rounded-lg border border-emerald-500/35 bg-emerald-500/15 px-2.5 py-1 text-[11px] font-medium text-emerald-50/95 hover:bg-emerald-500/25 disabled:opacity-50"
                          onClick={() =>
                            void approvePermissionRequest(
                              m.permissionRequired!.permission_request_id,
                              "once",
                            )
                          }
                        >
                          Allow once
                        </button>
                        <button
                          type="button"
                          disabled={
                            permissionBusyId === m.permissionRequired.permission_request_id
                          }
                          className="rounded-lg border border-cyan-500/35 bg-cyan-500/15 px-2.5 py-1 text-[11px] font-medium text-cyan-50/95 hover:bg-cyan-500/25 disabled:opacity-50"
                          onClick={() =>
                            void approvePermissionRequest(
                              m.permissionRequired!.permission_request_id,
                              "session",
                            )
                          }
                        >
                          Allow for session
                        </button>
                        <button
                          type="button"
                          disabled={
                            permissionBusyId === m.permissionRequired.permission_request_id
                          }
                          className="rounded-lg border border-white/15 bg-white/[0.06] px-2.5 py-1 text-[11px] text-zinc-200 hover:bg-white/10 disabled:opacity-50"
                          onClick={() =>
                            void denyPermissionRequest(m.permissionRequired!.permission_request_id)
                          }
                        >
                          Deny
                        </button>
                      </div>
                    </div>
                  )}
                  {m.web_tool_line &&
                    m.agent_key === "marketing" &&
                    m.response_kind !== "marketing_web_analysis" && (
                    <p className="mt-1.5 pl-0.5 text-[10px] text-zinc-500">
                      {m.web_tool_line}
                    </p>
                  )}
              {(m.decision || m.web_tool_line || (m.sources && m.sources[0]) || m.usage_subline) && (
                <details className="mt-1.5 text-[10px] text-zinc-500">
                  <summary className="cursor-pointer list-none pl-0 marker:content-[''] [&::-webkit-details-marker]:hidden text-zinc-500 hover:text-zinc-300">
                    <span className="underline decoration-dotted decoration-zinc-600/50">What Nexa used</span>
                  </summary>
                  <div className="mt-1.5 max-w-full space-y-0.5 break-words pl-0 text-zinc-500">
                    {m.decision && (
                      <p>
                        <span className="text-zinc-600">Action: </span>
                        {m.decision.action} · {m.decision.tool || "—"}
                      </p>
                    )}
                    {m.web_tool_line && (
                      <p>
                        <span className="text-zinc-600">Line: </span>
                        {m.web_tool_line}
                      </p>
                    )}
                    {m.sources && m.sources[0] && (
                      <p>
                        <span className="text-zinc-600">Source: </span>
                        {m.sources[0].url}
                      </p>
                    )}
                    {costDetailOn && m.usage_subline && (
                      <p>
                        <span className="text-zinc-600">Usage: </span>
                        {m.usage_subline}
                      </p>
                    )}
                  </div>
                </details>
              )}
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px]">
                    <span className="text-zinc-500">
                      {exportingMessageId === m.id ? "Creating document…" : "Export"}
                    </span>
                    {(
                      [
                        ["PDF", "pdf" as const],
                        ["Word", "docx" as const],
                        ["Markdown", "md" as const],
                        ["Text", "txt" as const],
                      ] as const
                    ).map(([label, fmt]) => (
                      <button
                        key={fmt}
                        type="button"
                        disabled={exportingMessageId === m.id}
                        onClick={() => {
                          void exportAssistantMessage(m, fmt);
                        }}
                        className="rounded border border-white/10 bg-white/[0.03] px-1.5 py-0.5 text-zinc-300 hover:border-white/20 hover:bg-white/[0.08] disabled:opacity-50"
                        title={`Download ${label}`}
                      >
                        {exportingMessageId === m.id ? "…" : label}
                      </button>
                    ))}
                  </div>
                  {m.exportInfo && (
                    <p className="mt-1.5 text-[10px] text-zinc-500">
                      <span className="text-zinc-400">Exported:</span> {m.exportInfo.format.toUpperCase()} ·{" "}
                      <button
                        type="button"
                        className="text-cyan-300/90 underline decoration-cyan-500/30 hover:text-cyan-200"
                        onClick={() => {
                          void (async () => {
                            try {
                              const b = await webDownloadBlob(m.exportInfo!.path);
                              const ex =
                                m.exportInfo!.format === "docx"
                                  ? "docx"
                                  : m.exportInfo!.format === "pdf"
                                    ? "pdf"
                                    : m.exportInfo!.format === "md"
                                      ? "md"
                                      : "txt";
                              downloadBlobToFile(b, `nexa-doc-${m.exportInfo!.docId}.${ex}`);
                            } catch (e) {
                              showToast((e as Error).message);
                            }
                          })();
                        }}
                      >
                        Download
                      </button>
                    </p>
                  )}
                  {m.decision && (
                    <details className="mt-1 text-xs text-zinc-500 group/dec">
                      <summary className="cursor-pointer list-none pl-0 marker:content-[''] [&::-webkit-details-marker]:hidden">
                        <span className="underline decoration-zinc-600/60 decoration-dotted">
                          Why this response? {decisionCollapsedLine(m.decision)}
                        </span>
                      </summary>
                      <div className="mt-1.5 space-y-0.5 pl-0 text-zinc-500">
                        <p>
                          <span className="text-zinc-600">Reason: </span>
                          {m.decision.reason}
                        </p>
                        <p>
                          <span className="text-zinc-600">Approval: </span>
                          {m.decision.approval_required
                            ? "Required before the agent can make changes"
                            : "Not required."}
                        </p>
                        <p>
                          <span className="text-zinc-600">Tool: </span>
                          {m.decision.tool?.replace(/_/g, " ") || "—"}
                        </p>
                        <p>
                          <span className="text-zinc-600">Risk: </span>
                          {m.decision.risk}
                        </p>
                      </div>
                    </details>
                  )}
                  {m.related_jobs && m.related_jobs[0] && (
                    <p className="mb-1 mt-2 text-[10px] text-zinc-500">
                      <span className="text-zinc-400">Agent selected:</span> {agentLabel(m.related_jobs[0]!.worker_type || m.agent_key)}{" "}
                      · <span className="text-zinc-400">Tool</span>{" "}
                      {(m.related_jobs[0]!.payload_json?.execution_decision as { tool_key?: string } | undefined)?.tool_key || "aider"}{" "}
                      · <span className="text-zinc-400">Mode</span>{" "}
                      {(m.related_jobs[0]!.payload_json?.execution_decision as { mode?: string } | undefined)?.mode || "—"}{" "}
                      · <span className="text-zinc-400">Risk</span>{" "}
                      {m.related_jobs[0]!.risk_level || "—"}
                    </p>
                  )}
                  {m.related_jobs && m.related_jobs.length > 0 && (
                    <div className="mt-2 space-y-2 pl-0">
                      {m.related_jobs.map((j) => {
                        const live = jobById[j.id] || j;
                        return <JobInlineCard key={j.id} job={live} onUpdated={mergeJob} onNotify={showToast} />;
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
            );
          })}
          {sending && (
            <div className={`mx-auto flex min-w-0 items-center gap-2 text-xs text-zinc-500 ${CHAT_COMPOSER_MAX}`}>
              <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-violet-400" aria-hidden />
              {sendingActivity}
            </div>
          )}
        </div>

        <div className="border-t border-white/10 bg-gradient-to-b from-zinc-950/80 to-black/90 py-3">
          <div className={`mx-auto mb-2 flex min-w-0 flex-wrap gap-1.5 ${CHAT_COMPOSER_MAX}`}>
            {composerAgentChips.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  setInput((prev) => (prev && !prev.endsWith(" ") ? `${prev} ${c.insert}` : `${prev}${c.insert}`));
                  setSuggest([]);
                  inputRef.current?.focus();
                }}
                className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] text-zinc-300 hover:border-emerald-500/30 hover:bg-white/10 hover:text-zinc-100"
              >
                {c.label}
              </button>
            ))}
          </div>
          {(!input.trim() || input === "/") && (
            <div className={`mx-auto mb-2 min-w-0 ${CHAT_COMPOSER_MAX}`}>
              <button
                type="button"
                onClick={() => setCommandHintsOpen((o) => !o)}
                className="flex w-full min-w-0 items-center gap-1.5 rounded py-1 text-left text-[11px] text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200"
                aria-expanded={commandHintsOpen}
                aria-controls="nexa-command-hints"
                id="nexa-command-hints-toggle"
              >
                <span className="inline-flex shrink-0 text-zinc-500" aria-hidden>
                  {commandHintsOpen ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                </span>
                Command hints
              </button>
              {commandHintsOpen && (
                <ul
                  id="nexa-command-hints"
                  className="mt-1 max-w-full list-none space-y-0.5 pl-0 text-left text-[11px] text-zinc-500"
                  aria-labelledby="nexa-command-hints-toggle"
                >
                  <li className="text-[10px] text-zinc-600">Click to fill</li>
                  {SLASH_HINTS.map((h) => (
                    <li key={h.cmd} className="ml-0">
                      <button
                        type="button"
                        onClick={() => {
                          setInput(h.fill);
                          setSuggest([]);
                          inputRef.current?.focus();
                        }}
                        className="w-full max-w-full truncate text-left text-zinc-300 hover:underline"
                      >
                        {h.cmd} <span className="text-zinc-600">— {h.help}</span>
                      </button>
                    </li>
                  ))}
                  <li className="mt-2 text-zinc-500">Web access (read-only)</li>
                  {[RESEARCH_URL_CHIP, webSearchChip, browserPreviewChip, ...PUBLIC_URL_CHIPS].map((h) => (
                    <li key={h.fill} className="ml-0">
                      <button
                        type="button"
                        onClick={() => {
                          setInput(h.fill.endsWith("https://") ? h.fill : `${h.fill} `);
                          setSuggest([]);
                          inputRef.current?.focus();
                        }}
                        className="w-full max-w-full truncate text-left text-zinc-300 hover:underline"
                      >
                        {h.fill} <span className="text-zinc-600">— {h.help}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {suggest.length > 0 && input.trim().length >= 1 && (
            <ul className={`mx-auto mb-1 min-w-0 list-none pl-0 text-left text-xs text-zinc-400 ${CHAT_COMPOSER_MAX}`}>
              {suggest.map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    onClick={() => {
                      setInput(s);
                      setSuggest([]);
                    }}
                    className="w-full max-w-full truncate rounded px-1 py-0.5 text-left text-zinc-200 hover:bg-white/10"
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className={`relative mx-auto min-w-0 ${CHAT_COMPOSER_MAX}`}>
            <textarea
              ref={inputRef}
              rows={2}
              className="w-full resize-y rounded-2xl border border-white/15 bg-[#0e0e10] py-2.5 pl-3.5 pr-3 text-sm text-zinc-100 shadow-inner outline-none transition placeholder:text-zinc-500 focus:border-emerald-500/40"
              value={input}
              onChange={(e) => onType(e.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Type a message, @nexa or a user agent, run dev: …, or paste a public URL."
            />
            <div className="mt-1.5 flex justify-end gap-2">
              <p className="self-center pr-1 text-[10px] text-zinc-500">Enter to send · Shift+Enter for new line</p>
              <button
                type="button"
                onClick={() => void send()}
                disabled={sending || !input.trim()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-b from-emerald-400/90 to-emerald-500/60 px-4 py-1.5 text-sm font-medium text-zinc-950 disabled:opacity-50"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Send
              </button>
            </div>
          </div>
        </div>
      </div>

      {toast && (
        <div
          role="status"
          className="pointer-events-none fixed bottom-4 right-4 z-50 max-w-sm rounded border border-zinc-700/80 bg-zinc-900/95 px-3 py-2 text-sm text-zinc-100 shadow-lg"
        >
          {toast}
        </div>
      )}

      {rightOpen && (
        <>
          <div
            role="separator"
            aria-label="Drag to resize side panel"
            aria-orientation="vertical"
            onMouseDown={startResizeRight}
            title="Drag to resize side panel"
            className="group relative w-1.5 shrink-0 cursor-col-resize select-none border-l border-r border-transparent bg-transparent hover:border-white/20 hover:bg-white/5"
          >
            <span
              className="pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-zinc-600/80 group-hover:bg-zinc-500"
              aria-hidden
            />
          </div>
        <aside
            className="flex h-full min-h-0 min-w-0 max-w-[600px] flex-col bg-[#0a0a0c]"
            style={{ width: rightPanelWidth, minWidth: RIGHT_PANEL_W_MIN, maxWidth: RIGHT_PANEL_W_MAX }}
        >
          <div className="flex shrink-0 gap-0.5 border-b border-white/10 p-1.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
            {(
              [
                ["job", "Job"],
                ["memory", "Memory"],
                ["system", "System"],
                ["keys", "Keys"],
                ["usage", "Usage"],
                ["docs", "Docs"],
              ] as [RightTab, string][]
            ).map(([tab, label]) => (
              <button
                key={tab}
                type="button"
                onClick={() => setRightTab(tab)}
                className={`flex-1 rounded py-1.5 ${rightTab === tab ? "bg-white/10 text-white" : "text-zinc-500 hover:text-zinc-200"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-3 text-sm">
            {rightTab === "job" && (
              <div className="text-zinc-300">
                {workContext && (workContext.lines.length > 0 || (workContext.recent_artifacts?.length ?? 0) > 0) && (
                  <div className="mb-3 rounded border border-white/10 bg-white/[0.02] p-2.5 text-[10px] leading-relaxed text-zinc-500">
                    <h4 className="mb-1.5 text-[9px] font-medium uppercase tracking-wide text-zinc-500">
                      Current work
                    </h4>
                    {workContext.lines.length > 0 && (
                      <ul className="list-none space-y-0.5 pl-0 text-zinc-400">
                        {workContext.lines.map((line, i) => (
                          <li key={i}>{line}</li>
                        ))}
                      </ul>
                    )}
                    {workContext.recent_artifacts && workContext.recent_artifacts.length > 0 && (
                      <p className="mt-1.5 border-t border-white/5 pt-1.5 text-[9px] text-zinc-500">
                        <span className="text-zinc-600">Recent artifacts: </span>
                        {workContext.recent_artifacts
                          .slice(0, 4)
                          .map((a) => a.label)
                          .join(" · ")}
                      </p>
                    )}
                  </div>
                )}
                <h3 className="text-xs font-semibold uppercase text-zinc-500">Focused</h3>
                {focusJobId && jobById[focusJobId] ? (
                  <div className="mt-2">
                    <JobInlineCard job={jobById[focusJobId]!} onUpdated={mergeJob} onNotify={showToast} />
                  </div>
                ) : (
                  <p className="mt-1 text-xs text-zinc-500">Select a job below or ask Nexa in chat.</p>
                )}
                {jobPanelList === null && <p className="mt-3 text-xs text-zinc-500">Syncing full job list…</p>}
                {jobPanelList !== null && allJobsForPanel.length === 0 && (
                  <p className="mt-2 text-sm text-zinc-500">No active jobs yet. Ask Nexa to create one.</p>
                )}
                {allJobsForPanel.length > 0 && (
                  <div className="mt-4 space-y-4 text-xs">
                    {jobGroups.active.length > 0 && (
                      <div>
                        <h4 className="font-semibold uppercase text-zinc-500">Active</h4>
                        <div className="mt-1 space-y-1">
                          {jobGroups.active.map((j) => (
                            <JobRowMini
                              key={j.id}
                              job={j}
                              onPick={(jid) => {
                                setFocusJobId(jid);
                                void webFetch<NexaJob>(`/web/jobs/${jid}`).then(mergeJob).catch(() => {
                                  /* */
                                });
                              }}
                            />
                          ))}
                        </div>
                      </div>
                    )}
                    {jobGroups.need.length > 0 && (
                      <div>
                        <h4 className="font-semibold uppercase text-amber-500/90">Needs action</h4>
                        <div className="mt-1 space-y-2">
                          {jobGroups.need.map((j) => {
                            const live = jobById[j.id] || j;
                            return <JobInlineCard key={j.id} job={live} onUpdated={mergeJob} onNotify={showToast} />;
                          })}
                        </div>
                      </div>
                    )}
                    {jobGroups.hist.length > 0 && (
                      <div>
                        <h4 className="font-semibold uppercase text-zinc-500">Recent history</h4>
                        <div className="mt-1 space-y-1">
                          {jobGroups.hist.map((j) => (
                            <JobRowMini
                              key={j.id}
                              job={j}
                              onPick={(jid) => {
                                setFocusJobId(jid);
                                void webFetch<NexaJob>(`/web/jobs/${jid}`).then(mergeJob).catch(() => {
                                  /* */
                                });
                              }}
                            />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {rightTab === "memory" && (
              <div className="text-zinc-200">
                {memErr && <p className="text-xs text-rose-300/90">{memErr}</p>}
                {!mem && !memErr && <p className="text-zinc-500">Loading…</p>}
                {mem && (
                  <div>
                    <p className="text-xs text-zinc-500">Memory is synced from the API (see Memory panel and nexa-memory documents).</p>
                    <label className="mt-3 block text-xs text-zinc-500">
                      Search memory
                      <input
                        className="mt-1 w-full rounded border border-zinc-800 bg-zinc-900/80 px-2 py-1 text-sm text-zinc-100"
                        value={memoryQuery}
                        onChange={(e) => setMemoryQuery(e.target.value)}
                        placeholder="Filter notes…"
                        aria-label="Search memory"
                      />
                    </label>
                    {filteredMemNotes && filteredMemNotes.length > 0 ? (
                      <ul className="mt-2 space-y-1.5">
                        {filteredMemNotes.slice(0, 20).map((n) => (
                          <li key={n.key} className="rounded-lg border border-white/5 bg-white/[0.04] p-2 text-xs text-zinc-200">
                            <p className="line-clamp-1 text-zinc-500">{(n.category || "note") + (n.key ? " · " + n.key : "")}</p>
                            {n.summary || n.content}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-zinc-500">No notes match{memoryQuery ? " that search" : " yet"}.</p>
                    )}
                    <p className="mt-3 text-xs text-zinc-500">Add to memory: use the chat and memory commands, or your usual Telegram flow.</p>
                    <details className="mt-2 text-zinc-500">
                      <summary className="cursor-pointer text-xs">Advanced — full soul & memory (markdown)</summary>
                      <pre className="mt-1 max-h-32 overflow-auto text-[9px] text-zinc-400">
                        {mem.soul_markdown
                          ? `--- soul.md ---\n${mem.soul_markdown.slice(0, 6_000)}${
                              mem.soul_markdown.length > 6_000 ? "\n…" : ""
                            }`
                          : "No soul on disk in this state."}
                      </pre>
                    </details>
                  </div>
                )}
              </div>
            )}

            {rightTab === "system" && (
              <div>
                <div className="mb-3 rounded border border-white/5 bg-white/[0.02] p-2.5">
                  <div className="mb-1.5 flex items-center justify-between gap-1">
                    <p className="text-[11px] font-medium text-zinc-200">What’s new</p>
                    <button
                      type="button"
                      onClick={() => void loadReleaseLatest()}
                      disabled={releaseLoad}
                      className="inline-flex items-center gap-0.5 text-[10px] text-cyan-400/90 hover:underline disabled:opacity-50"
                      title="Refresh release notes"
                    >
                      {releaseLoad ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                      Refresh
                    </button>
                  </div>
                  {releaseErr && <p className="text-[10px] text-rose-300/80">{releaseErr}</p>}
                  {releaseLoad && !releaseLatest && !releaseErr && <p className="text-xs text-zinc-500">Loading…</p>}
                  {releaseLatest && (
                    <div>
                      {releaseLatest.release_id && (
                        <p className="text-[10px] text-zinc-500">Release: {releaseLatest.release_id}</p>
                      )}
                      {releaseLatest.items && releaseLatest.items.length > 0 ? (
                        <ul className="mt-1.5 list-disc space-y-0.5 pl-3.5 text-[10px] text-zinc-300">
                          {releaseLatest.items.slice(0, 10).map((t, idx) => (
                            <li key={idx} className="[overflow-wrap:anywhere] break-words">
                              {t}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-[10px] text-zinc-500">No highlights listed for this cut.</p>
                      )}
                    </div>
                  )}
                </div>
                <div className="mb-2 flex flex-wrap items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => void refetchSystemStatus()}
                    disabled={systemRefreshing}
                    className="inline-flex items-center gap-1 rounded border border-zinc-700 bg-zinc-800/50 px-2 py-1 text-[10px] text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
                    title="Refresh system status"
                    aria-label="Refresh system status"
                  >
                    {systemRefreshing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                    Refresh
                  </button>
                  <Link
                    href="/mission-control"
                    className="inline-flex items-center gap-1 rounded border border-violet-500/35 bg-violet-500/10 px-2 py-1 text-[10px] font-medium text-violet-200/95 hover:bg-violet-500/20"
                  >
                    <LayoutDashboard className="h-3 w-3 shrink-0" aria-hidden />
                    Mission Control
                  </Link>
                  <Link
                    href="/trust"
                    className="inline-flex items-center gap-1 rounded border border-emerald-500/35 bg-emerald-500/10 px-2 py-1 text-[10px] font-medium text-emerald-200/95 hover:bg-emerald-500/20"
                  >
                    <Shield className="h-3 w-3 shrink-0" aria-hidden />
                    Trust & activity
                  </Link>
                </div>
                <GovernancePanel />
                <div className="mb-3 rounded border border-cyan-500/15 bg-cyan-500/[0.04] p-2.5">
                  <p className="text-[11px] font-medium text-zinc-200">Channels</p>
                  <p className="mt-1 text-[10px] text-zinc-500">
                    Gateway endpoints and required env vars — values are never shown here.
                  </p>
                  <div className="mt-2">
                    <ChannelAdminPanel
                      data={channelsData}
                      error={channelsErr}
                      onCopied={() => showToast("Copied")}
                    />
                  </div>
                </div>
                {hostExecutor && (
                  <div className="mb-3 rounded border border-emerald-500/15 bg-emerald-500/[0.04] p-2.5">
                    <p className="text-[11px] font-medium text-zinc-200">Host executor</p>
                    <p className="mt-1 text-[10px] text-zinc-400">
                      Status:{" "}
                      <span className={hostExecutor.enabled ? "text-emerald-300/90" : "text-zinc-500"}>
                        {hostExecutor.enabled ? "enabled" : "disabled"}
                      </span>
                      {" · "}
                      Timeout {hostExecutor.timeout_seconds}s · Max file {Math.round(hostExecutor.max_file_bytes / 1024)} KiB
                    </p>
                    <p className="mt-1 break-all text-[10px] text-zinc-500" title={hostExecutor.work_root}>
                      Work root: <span className="text-zinc-400">{hostExecutor.work_root}</span>
                    </p>
                    <p className="mt-1 text-[10px] text-zinc-500">
                      Allowed host_action: {hostExecutor.allowed_host_actions.join(", ")}
                    </p>
                    <p className="mt-0.5 text-[10px] text-zinc-500">
                      Allowed run names: {hostExecutor.allowed_run_names.join(", ")}
                    </p>
                  </div>
                )}
                <div className="mb-3 rounded border border-white/10 bg-white/[0.02] p-2.5">
                  <p className="text-[11px] font-medium text-zinc-200">Permissions</p>
                  <p className="mt-1 text-[10px] text-zinc-500">
                    Scoped host-executor grants — grouped by scope. Grant type, path, risk, and last use are
                    always visible. Manage in Telegram with /permissions — revoke anytime.
                  </p>
                  {accessPanelErr && (
                    <p className="mt-1 text-[10px] text-rose-300/80">{accessPanelErr}</p>
                  )}
                  {accessPerms && activePermissionCount === 0 && (
                    <p className="mt-2 text-[10px] text-zinc-500">No active or pending permissions.</p>
                  )}
                  {permissionsDisplayGroups.length > 0 && (
                    <div className="mt-2 space-y-3">
                      {permissionsDisplayGroups.map(({ scope, rows }) => (
                        <div key={scope}>
                          <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                            {scope}
                          </p>
                          <ul className="mt-1 space-y-1.5">
                            {rows.map((p) => (
                              <li
                                key={p.id}
                                className="rounded border border-white/5 px-1.5 py-1 text-[10px] text-zinc-300"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <span className="text-zinc-400">#{p.id}</span>
                                  <span
                                    className={`rounded border px-1 py-px text-[9px] ${riskBadgeClasses(p.risk_level)}`}
                                  >
                                    {p.risk_level}
                                  </span>
                                  <span className="text-zinc-500">{p.status}</span>
                                </div>
                                <p className="mt-0.5 break-all text-zinc-500" title={p.target}>
                                  {p.target.length > 140 ? `${p.target.slice(0, 137)}…` : p.target}
                                </p>
                                <p className="mt-0.5 text-[9px] text-zinc-600">
                                  Last used: {formatPermissionLastUsed(p.last_used_at)}{" "}
                                  <span className="text-zinc-600">
                                    · Grant: {(p.grant_mode || "persistent").replace(/_/g, " ")}
                                  </span>
                                </p>
                                {(p.status === "granted" || p.status === "pending") && (
                                  <button
                                    type="button"
                                    disabled={permBusyId === p.id}
                                    onClick={() => void revokePermissionRow(p.id)}
                                    className="mt-1 text-[10px] text-rose-400/90 hover:underline disabled:opacity-50"
                                  >
                                    Revoke
                                  </button>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="mb-3 rounded border border-white/10 bg-white/[0.02] p-2.5">
                  <p className="text-[11px] font-medium text-zinc-200">Workspace projects</p>
                  <p className="mt-1 text-[10px] text-zinc-500">
                    Named folders under your roots — Nexa uses the active one as the default path for file intel in
                    this chat (no scanning). Telegram: /projects, /project use &lt;id&gt;.
                  </p>
                  {nexaWsProjects && nexaWsProjects.length === 0 && (
                    <p className="mt-2 text-[10px] text-zinc-500">
                      None yet — owner adds via /project add on Telegram or POST /web/workspace/nexa-projects.
                    </p>
                  )}
                  {nexaWsProjects && nexaWsProjects.length > 0 && (
                    <ul className="mt-2 space-y-1.5">
                      {nexaWsProjects.slice(0, 12).map((p) => (
                        <li
                          key={p.id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded border border-white/5 px-1.5 py-1 text-[10px] text-zinc-300"
                        >
                          <div className="min-w-0">
                            <span className="font-medium text-zinc-200">{p.name}</span>
                            <p className="break-all text-zinc-500" title={p.path_normalized}>
                              {p.path_normalized.length > 120
                                ? `${p.path_normalized.slice(0, 117)}…`
                                : p.path_normalized}
                            </p>
                          </div>
                          <button
                            type="button"
                            disabled={nexaWsBusyId !== null}
                            onClick={() => void activateNexaWorkspaceProject(p.id)}
                            className="shrink-0 text-[10px] text-cyan-400/90 hover:underline disabled:opacity-50"
                          >
                            Use in chat
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {nexaWsProjects && nexaWsProjects.length > 0 && (
                    <button
                      type="button"
                      disabled={nexaWsBusyId !== null}
                      onClick={() => void activateNexaWorkspaceProject(null)}
                      className="mt-2 text-[10px] text-zinc-500 hover:underline disabled:opacity-50"
                    >
                      Clear active project
                    </button>
                  )}
                </div>
                <div className="mb-3 rounded border border-white/10 bg-white/[0.02] p-2.5">
                  <p className="text-[11px] font-medium text-zinc-200">Workspace roots</p>
                  <p className="mt-1 text-[10px] text-zinc-500">
                    Registered safe folders when access enforcement is enabled (/workspace on Telegram).
                  </p>
                  {accessRoots && accessRoots.length === 0 && (
                    <p className="mt-2 text-[10px] text-zinc-500">
                      None registered — with enforcement off, the default work root may still apply.
                    </p>
                  )}
                  {accessRoots && accessRoots.length > 0 && (
                    <ul className="mt-2 space-y-1 text-[10px] text-zinc-400">
                      {accessRoots.map((r) => (
                        <li key={r.id} className="break-all">
                          #{r.id} {r.path_normalized}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                {systemErr && <p className="mb-2 text-xs text-rose-300/90">{systemErr}</p>}
                {sysInd && !systemErr && (
                  <ul className="space-y-1.5">
                    {sysInd.map((i) => (
                      <li key={i.id} className="flex items-start justify-between gap-2 rounded border border-white/5 px-1.5 py-1.5 text-xs text-zinc-200">
                        <div className="min-w-0">
                          <span className="block text-zinc-200">{i.label}</span>
                          {i.detail ? (
                            <span className="text-[10px] text-zinc-500" title={i.detail}>
                              {i.detail}
                            </span>
                          ) : null}
                        </div>
                        <span className={`shrink-0 ${indLevelClass(i.level)}`} title={i.detail || i.label}>
                          {i.level === "ok" ? "✅" : i.level === "error" ? "❌" : "⚠️"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {!sysInd && !systemErr && <p className="text-xs text-zinc-500">Loading…</p>}
                <details
                  className="mt-3"
                  onToggle={(e) => {
                    if ((e.target as HTMLDetailsElement).open) {
                      void loadDoctor();
                    }
                  }}
                >
                  <summary className="cursor-pointer text-xs text-zinc-400">Full doctor report (expand)</summary>
                  {doctor != null && !doctorErr && (
                    <div className="mb-1 mt-2">
                      <button
                        type="button"
                        onClick={copyDoctorReport}
                        className="inline-flex items-center gap-1 text-[10px] text-cyan-400/90 hover:underline"
                      >
                        <Copy className="h-3 w-3" /> Copy report
                      </button>
                    </div>
                  )}
                  {doctorLoading && <p className="mt-2 text-xs text-zinc-500">Loading…</p>}
                  {doctorErr && <p className="mt-2 text-xs text-rose-300/90">{doctorErr}</p>}
                  {doctor != null && !doctorErr && (
                    <pre className="mt-1 max-h-72 overflow-y-auto overflow-x-hidden rounded border border-white/5 bg-black/20 p-2 text-[9px] text-zinc-400 break-words whitespace-pre-wrap">
                      {doctor}
                    </pre>
                  )}
                </details>
              </div>
            )}

            {rightTab === "keys" && (
              <div className="text-xs text-zinc-300">
                {keysErr && <p className="mb-2 text-rose-300/90">{keysErr}</p>}
                {keys === null && !keysErr && (
                  <p className="flex items-center gap-1 text-zinc-500">
                    <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
                    Loading keys…
                  </p>
                )}
                {keys && (
                  <p className="text-zinc-500">
                    You can use Nexa with your own API key. Add OpenAI or Anthropic here. Keys are stored server-side, never in chat.
                  </p>
                )}
                {keys && (
                  <div className="mt-3 space-y-3">
                    {KEY_PROVIDERS.map((prov) => {
                      const row = keys!.find((x) => x.provider === prov);
                      const has = row?.has_key;
                      return (
                        <div key={prov} className="rounded border border-white/5 p-2.5">
                          <div className="flex items-center justify-between gap-1">
                            <span className="text-zinc-200 capitalize">{prov}</span>
                            {has && row ? (
                              <span className="text-emerald-200/80">connected · ···{row.last4}</span>
                            ) : (
                              <span className="text-zinc-500">not connected</span>
                            )}
                          </div>
                          {keyDraft === prov ? (
                            <div className="mt-2">
                              <input
                                type="password"
                                className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm text-zinc-100"
                                value={keyInput}
                                onChange={(e) => setKeyInput(e.target.value)}
                                placeholder="API key (never shared in chat)"
                                autoComplete="off"
                                disabled={keyBusy === prov}
                              />
                              <div className="mt-1.5 flex gap-1.5">
                                <button
                                  type="button"
                                  disabled={keyBusy === prov}
                                  onClick={() => void saveKeyForProvider(prov)}
                                  className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-200 disabled:opacity-50"
                                >
                                  {keyBusy === prov ? "Saving…" : "Save key"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setKeyDraft("");
                                    setKeyInput("");
                                  }}
                                  className="rounded border border-zinc-700 px-2 py-0.5 text-xs"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              <button
                                type="button"
                                className="rounded border border-zinc-700 bg-white/5 px-2 py-0.5 text-zinc-200 hover:border-zinc-500"
                                onClick={() => {
                                  setKeyDraft(prov);
                                  setKeyInput("");
                                }}
                              >
                                {has ? "Replace" : "Add"}
                              </button>
                              {has && (
                                <button
                                  type="button"
                                  className="rounded border border-rose-500/30 bg-rose-500/5 px-2 py-0.5 text-rose-200/90 hover:bg-rose-500/10 disabled:opacity-50"
                                  disabled={keyBusy === prov}
                                  onClick={() => void removeKeyForProvider(prov)}
                                >
                                  {keyBusy === prov ? "…" : "Remove"}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
                {keys && keys.length === 0 && !keysErr && (
                  <p className="mt-2 text-zinc-500">No key rows returned. Your user may need a Telegram id (tg_…) for this API.</p>
                )}
                <p className="mt-3 text-[9px] text-zinc-500">Use Connection settings for base URL. Never paste API keys in chat.</p>
              </div>
            )}

            {rightTab === "usage" && (
              <div className="space-y-3 text-xs text-zinc-300">
                <div className="flex items-center justify-between gap-1">
                  <h3 className="text-xs font-semibold text-zinc-200">Nexa usage (today)</h3>
                  <button
                    type="button"
                    onClick={() => void loadUsagePanel()}
                    disabled={usageLoad}
                    className="inline-flex items-center gap-1 rounded border border-zinc-700 bg-zinc-800/50 px-2 py-1 text-[10px] text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
                    aria-label="Refresh usage"
                  >
                    {usageLoad ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                    Refresh
                  </button>
                </div>
                <p className="text-[9px] leading-relaxed text-zinc-500">
                  Estimated cost only. Estimates are based on configured public model pricing and may differ from provider
                  billing.
                </p>
                <label className="mt-1 flex cursor-pointer items-center gap-1.5 text-[10px] text-zinc-500">
                  <input
                    type="checkbox"
                    className="rounded border-zinc-600 bg-zinc-900"
                    checked={costDetailOn}
                    onChange={(e) => {
                      const on = e.target.checked;
                      setCostDetailOn(on);
                      if (typeof window !== "undefined") {
                        localStorage.setItem(LS_SHOW_COST, on ? "true" : "false");
                      }
                    }}
                  />
                  Show per-message cost details
                </label>
                {usageErr && <p className="text-rose-300/90">{usageErr}</p>}
                {usage && !usageErr && (
                  <div className="rounded border border-white/5 bg-white/[0.04] p-2.5 text-[11px] text-zinc-200">
                    <p className="text-[10px] text-zinc-500">LLM activity (this period)</p>
                    <p className="mt-1">
                      Calls: <span className="text-zinc-100">{usage.total_calls}</span> — Tokens:{" "}
                      <span className="text-zinc-100">{usage.total_tokens.toLocaleString()}</span>
                    </p>
                    <p className="mt-0.5">
                      Estimated: <span className="text-zinc-100">${(usage.estimated_cost_usd ?? 0).toFixed(4)}</span> ·
                      System-key: <span className="text-zinc-100">${(usage.system_key_cost_usd ?? 0).toFixed(4)}</span>{" "}
                      · BYOK: <span className="text-zinc-100">${(usage.user_key_cost_usd ?? 0).toFixed(4)}</span>
                    </p>
                  </div>
                )}
                {usage && usage.efficiency && (usage.efficiency.total_actions ?? 0) > 0 && !usageErr && (
                  <div className="rounded border border-white/5 bg-white/[0.04] p-2.5 text-[10px] text-zinc-300">
                    <p className="font-medium text-zinc-200">Efficiency</p>
                    <p className="mt-0.5">
                      Actions: <span className="text-zinc-100">{usage.efficiency.total_actions}</span> · LLM calls:{" "}
                      <span className="text-zinc-100">{usage.efficiency.llm_calls}</span> · Tool-only:{" "}
                      <span className="text-zinc-100">{usage.efficiency.non_llm_actions}</span>
                    </p>
                    {usage.efficiency.efficiency_ratio != null ? (
                      <p className="mt-0.5 text-zinc-500">
                        Efficiency:{" "}
                        <span className="text-zinc-200">
                          {Math.round(usage.efficiency.efficiency_ratio * 100)}% without LLM
                        </span>
                      </p>
                    ) : null}
                  </div>
                )}
                {usage && usage.top_cost_drivers && usage.top_cost_drivers.length > 0 && !usageErr && (
                  <div>
                    <h4 className="text-[10px] font-medium text-zinc-200">Top cost drivers</h4>
                    <ul className="mt-0.5 list-none space-y-0.5 pl-0 text-[10px] text-zinc-400">
                      {usage.top_cost_drivers.map((d) => (
                        <li key={d.action}>
                          {d.action} — {d.percent}%
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {usage && (usage.by_provider.length > 0 || usage.by_agent.length > 0 || usage.by_action.length > 0) && (
                  <div className="space-y-2 text-[10px] text-zinc-400">
                    {usage.by_provider.length > 0 && (
                      <div>
                        <h4 className="font-medium text-zinc-200">By provider</h4>
                        <ul className="mt-0.5 space-y-0.5">
                          {usage.by_provider.slice(0, 6).map((b) => (
                            <li key={b.provider}>
                              {b.provider} · {b.calls} call(s) · {b.total_tokens.toLocaleString()} tok · $
                              {(b.estimated_cost_usd ?? 0).toFixed(4)}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {usage.by_agent.length > 0 && (
                      <div>
                        <h4 className="font-medium text-zinc-200">By agent</h4>
                        <ul className="mt-0.5 space-y-0.5">
                          {usage.by_agent.slice(0, 6).map((b) => (
                            <li key={b.agent || "none"}>
                              {agentLabel(b.agent)} · {b.calls} call(s) · {b.total_tokens.toLocaleString()} tok
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {usage.by_action.length > 0 && (
                      <div>
                        <h4 className="font-medium text-zinc-200">By action</h4>
                        <ul className="mt-0.5 space-y-0.5">
                          {usage.by_action.slice(0, 8).map((b) => (
                            <li key={b.action || "none"}>
                              {b.action || "—"} · {b.calls} call(s) · {b.total_tokens.toLocaleString()} tok
                              {b.percent != null ? ` · ${b.percent}%` : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
                {usageRecent && usageRecent.length > 0 && !usageErr && (
                  <div>
                    <h4 className="text-[10px] font-medium uppercase text-zinc-500">Recent</h4>
                    <ul className="mt-1 max-h-36 space-y-0.5 overflow-y-auto text-[10px] text-zinc-400">
                      {usageRecent.slice(0, 20).map((r, i) => (
                        <li key={`${r.at || ""}-${i}`} className="line-clamp-1">
                          {r.action || "—"} · {r.provider} · {r.total_tokens.toLocaleString()} tok ·
                          {r.estimated_cost_usd != null ? ` $${Number(r.estimated_cost_usd).toFixed(4)}` : " —"} ·
                          {r.used_user_key ? "BYOK" : "System"}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="text-[9px] leading-relaxed text-zinc-500">
                  <p className="text-zinc-400">Why Nexa is efficient</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4 text-zinc-500">
                    <li>skips unnecessary LLM calls</li>
                    <li>uses tools before reasoning</li>
                    <li>minimizes context size</li>
                    <li>avoids recursive agent loops</li>
                  </ul>
                </div>
              </div>
            )}

            {rightTab === "docs" && (
              <div className="text-xs text-zinc-300">
                <h3 className="text-xs font-semibold text-zinc-200">Generated documents</h3>
                <p className="mt-1 text-[10px] text-zinc-500">
                  PDF, Word, Markdown, and text exports are stored for your account. Retention is configured on the
                  host (`NEXA_DOCUMENT_RETENTION_DAYS`).
                </p>
                {docErr && <p className="mt-2 text-rose-300/90">{docErr}</p>}
                {docLoad && <p className="mt-2 text-zinc-500">Loading…</p>}
                {!docLoad && docList && docList.length === 0 && !docErr && (
                  <p className="mt-3 text-sm text-zinc-500">
                    No documents yet. Export an assistant response or ask Nexa to create a PDF.
                  </p>
                )}
                {!docLoad && docList && docList.length > 0 && (
                  <ul className="mt-2 space-y-2">
                    {docList.map((d) => (
                      <li
                        key={d.id}
                        className="rounded border border-white/5 bg-white/[0.04] px-2.5 py-2 text-[11px] text-zinc-200"
                      >
                        <p className="line-clamp-2 font-medium text-zinc-100">{d.title || "—"}</p>
                        <p className="mt-0.5 text-[10px] text-zinc-500">
                          {d.format.toUpperCase()} · {d.source_type} · {new Date(d.created_at).toLocaleString()}
                        </p>
                        <button
                          type="button"
                          className="mt-1.5 text-[10px] text-cyan-300/90 underline decoration-cyan-500/30 hover:text-cyan-200"
                          onClick={() => {
                            void (async () => {
                              try {
                                const blob = await webDownloadBlob(d.download_url);
                                const ex = d.format === "docx" ? "docx" : d.format === "pdf" ? "pdf" : d.format === "md" ? "md" : "txt";
                                downloadBlobToFile(blob, `nexa-doc-${d.id}.${ex}`);
                                showToast("Downloaded");
                              } catch (e) {
                                showToast((e as Error).message);
                              }
                            })();
                          }}
                        >
                          Download
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <button
                  type="button"
                  onClick={() => void loadDocList()}
                  className="mt-3 text-[10px] text-zinc-500 underline decoration-zinc-600 hover:text-zinc-300"
                >
                  Refresh list
                </button>
              </div>
            )}
          </div>
        </aside>
        </>
      )}
    </div>
  );
}

function Inner() {
  const [auth, setAuth] = useState<"unknown" | "no" | "yes">("unknown");
  useEffect(() => {
    setAuth(readConfig().userId ? "yes" : "no");
  }, []);
  if (auth === "unknown") {
    return <LoadingShell />;
  }
  if (auth === "no") {
    return <UnconfiguredPrompt />;
  }
  return <WorkspaceBody />;
}

export function WorkspaceApp() {
  return (
    <Suspense fallback={<div className="flex h-48 w-full items-center justify-center text-zinc-500">…</div>}>
      <Inner />
    </Suspense>
  );
}
