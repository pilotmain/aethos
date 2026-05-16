"use client";

import { Loader2, Wrench } from "lucide-react";

type DevRun = {
  id?: string;
  goal?: string;
  status?: string;
  workspace_id?: string;
  summary?: string | null;
  progress_messages?: string[] | null;
  error?: string | null;
};

type McTask = {
  mission_id?: string;
  agent_handle?: string;
  status?: string;
};

type AutonomousTask = Record<string, unknown>;

function isActiveStatus(s: string | undefined): boolean {
  const t = (s || "").toLowerCase();
  return t === "running" || t === "queued" || t === "pending" || t === "in_progress";
}

/** Human-readable “what AethOS is doing” from Mission Control snapshot. */
export function ActiveWorkPanel(props: {
  shellLight: boolean;
  devRuns?: DevRun[] | null;
  missionTasks?: McTask[] | null;
  autonomousTasks?: AutonomousTask[] | null;
  loading?: boolean;
}) {
  const { shellLight, devRuns, missionTasks, autonomousTasks, loading } = props;

  const activeDev = (devRuns || []).filter((r) => isActiveStatus(r.status));
  const activeMission = (missionTasks || []).filter((t) => isActiveStatus(t.status));
  const auto = (autonomousTasks || []).filter((t) => {
    const st = String(t.status ?? t.state ?? "").toLowerCase();
    return isActiveStatus(st);
  });

  const cardTitle = shellLight ? "text-zinc-900" : "text-zinc-100";
  const muted = shellLight ? "text-zinc-500" : "text-zinc-500";
  const line = shellLight ? "text-zinc-800" : "text-zinc-200";

  const lines: string[] = [];
  for (const r of activeDev.slice(0, 6)) {
    const g = (r.goal || "Dev investigation").trim();
    const head = g.length > 100 ? `${g.slice(0, 97)}…` : g;
    const msgs = Array.isArray(r.progress_messages)
      ? r.progress_messages.filter((m): m is string => typeof m === "string" && m.trim().length > 0)
      : [];
    const latest = msgs.length ? msgs[msgs.length - 1]!.trim() : "";
    const summ = typeof r.summary === "string" ? r.summary.trim() : "";
    const err = typeof r.error === "string" ? r.error.trim() : "";
    let tail = "";
    if (err) {
      tail = err.length > 140 ? `${err.slice(0, 137)}…` : err;
      lines.push(`${head} — blocked: ${tail}`);
      continue;
    }
    if (latest) {
      tail = latest.length > 160 ? `${latest.slice(0, 157)}…` : latest;
      lines.push(`${head} — ${tail}`);
      continue;
    }
    if (summ) {
      tail = summ.length > 140 ? `${summ.slice(0, 137)}…` : summ;
      lines.push(`${head} — ${tail}`);
      continue;
    }
    lines.push(head);
  }
  for (const t of activeMission.slice(0, 4)) {
    const h = (t.agent_handle || "agent").trim();
    lines.push(`Mission task · ${h}`);
  }
  for (const a of auto.slice(0, 4)) {
    const title = String(a.title ?? a.goal ?? a.name ?? "Autonomous task").trim();
    lines.push(title.length > 100 ? `${title.slice(0, 97)}…` : title);
  }

  return (
    <section
      className={`rounded-xl border p-4 transition-colors duration-300 ${
        shellLight ? "border-zinc-200/90 bg-white/95" : "border-zinc-800/60 bg-zinc-950/40"
      }`}
    >
      <div className="mb-2 flex items-center gap-2">
        <Wrench className={`h-4 w-4 ${shellLight ? "text-zinc-600" : "text-zinc-400"}`} aria-hidden />
        <h2 className={`text-sm font-semibold ${cardTitle}`}>What AethOS is doing now</h2>
        {loading ? (
          <Loader2
            className={`h-3.5 w-3.5 animate-spin ${shellLight ? "text-zinc-500" : "text-zinc-500"}`}
            aria-label="Loading"
          />
        ) : null}
      </div>
      <p className={`mb-2 text-[11px] ${muted}`}>
        Live dev runs, mission work, and autonomy — from your workspace and runtime state.
      </p>
      {lines.length === 0 ? (
        <p className={`text-xs ${muted}`}>
          No active work in the queue. When you ask AethOS to fix tests or run a dev mission, progress appears
          here.
        </p>
      ) : (
        <ul className="list-inside list-disc space-y-1.5 text-xs">
          {lines.map((x, i) => (
            <li key={i} className={line}>
              {x}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
