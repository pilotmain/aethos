"use client";

import { Brain, CalendarClock, Puzzle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { webFetch } from "@/lib/api";
import { isConfigured } from "@/lib/config";

type NexaMemoryResponse = { entry_count?: number; entries?: unknown[] };
type SchedulerListResponse = { jobs?: unknown[] };
type SkillsListResponse = { skills?: unknown[] };

/** Phase 22 — Memory, scheduler, and skills snapshot cards (Mission Control v3). */
export function Phase22Overview(props: {
  shellLight: boolean;
  /** Phase 42 — counts from unified Mission Control state (optional). */
  longRunningCount?: number;
  schedulerJobCount?: number;
  channelEventsCount?: number;
  autonomous?: boolean;
}) {
  const { shellLight, longRunningCount, schedulerJobCount, channelEventsCount, autonomous } = props;
  const [memory, setMemory] = useState<NexaMemoryResponse | null>(null);
  const [sched, setSched] = useState<SchedulerListResponse | null>(null);
  const [skills, setSkills] = useState<SkillsListResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!isConfigured()) return;
    setLoading(true);
    setErr(null);
    try {
      const [m, s, k] = await Promise.all([
        webFetch<NexaMemoryResponse>("/nexa-memory"),
        webFetch<SchedulerListResponse>("/scheduler/list"),
        webFetch<SkillsListResponse>("/skills"),
      ]);
      setMemory(m);
      setSched(s);
      setSkills(k);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setMemory(null);
      setSched(null);
      setSkills(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isConfigured()) return null;

  const cardTitle = shellLight ? "text-zinc-600" : "text-zinc-400";
  const stat = shellLight ? "text-zinc-900" : "text-zinc-50";

  return (
    <section
      className={`rounded-xl border p-4 transition-colors duration-300 ${
        shellLight ? "border-zinc-200 bg-white/90" : "border-zinc-800/80 bg-zinc-950/50"
      }`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className={`text-sm font-semibold ${shellLight ? "text-zinc-900" : "text-zinc-100"}`}>
          Autonomy layer
        </h2>
        <button
          type="button"
          onClick={() => void load()}
          className={`rounded-md border px-2 py-1 text-xs ${
            shellLight
              ? "border-zinc-300 bg-zinc-50 text-zinc-800 hover:bg-zinc-100"
              : "border-zinc-600 bg-zinc-900 text-zinc-200 hover:bg-zinc-800"
          }`}
          disabled={loading}
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {err ? (
        <p className={`mb-2 text-xs ${shellLight ? "text-rose-700" : "text-rose-300"}`}>{err}</p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-3">
        <div
          className={`rounded-lg border p-3 ${
            shellLight ? "border-zinc-200 bg-white text-zinc-900" : "border-zinc-700/80 bg-zinc-900/40 text-zinc-100"
          }`}
        >
          <div className={`mb-1 flex items-center gap-2 text-xs font-medium ${cardTitle}`}>
            <Brain className="h-4 w-4 shrink-0" aria-hidden />
            Persistent memory
          </div>
          <p className={`text-2xl font-semibold tabular-nums ${stat}`}>
            {memory?.entry_count ?? "—"}
          </p>
          <p className={`mt-1 text-[11px] ${cardTitle}`}>Entries (nexa-memory)</p>
        </div>
        <div
          className={`rounded-lg border p-3 ${
            shellLight ? "border-zinc-200 bg-white text-zinc-900" : "border-zinc-700/80 bg-zinc-900/40 text-zinc-100"
          }`}
        >
          <div className={`mb-1 flex items-center gap-2 text-xs font-medium ${cardTitle}`}>
            <CalendarClock className="h-4 w-4 shrink-0" aria-hidden />
            Scheduler
          </div>
          <p className={`text-2xl font-semibold tabular-nums ${stat}`}>
            {sched?.jobs?.length ?? "—"}
          </p>
          <p className={`mt-1 text-[11px] ${cardTitle}`}>Jobs (cron / interval)</p>
        </div>
        <div
          className={`rounded-lg border p-3 ${
            shellLight ? "border-zinc-200 bg-white text-zinc-900" : "border-zinc-700/80 bg-zinc-900/40 text-zinc-100"
          }`}
        >
          <div className={`mb-1 flex items-center gap-2 text-xs font-medium ${cardTitle}`}>
            <Puzzle className="h-4 w-4 shrink-0" aria-hidden />
            Skills
          </div>
          <p className={`text-2xl font-semibold tabular-nums ${stat}`}>
            {skills?.skills?.length ?? "—"}
          </p>
          <p className={`mt-1 text-[11px] ${cardTitle}`}>User-defined JSON skills</p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div
            className={`rounded-lg border p-3 ${
              shellLight ? "border-zinc-200 bg-white text-zinc-900" : "border-zinc-700/80 bg-zinc-900/40 text-zinc-100"
            }`}
          >
            <div className={`mb-1 text-xs font-medium ${cardTitle}`}>Long-running sessions</div>
            <p className={`text-2xl font-semibold tabular-nums ${stat}`}>
              {typeof longRunningCount === "number" ? longRunningCount : "—"}
            </p>
            <p className={`mt-1 text-[11px] ${cardTitle}`}>DB-backed sessions</p>
          </div>
          <div
            className={`rounded-lg border p-3 ${
              shellLight ? "border-zinc-200 bg-white text-zinc-900" : "border-zinc-700/80 bg-zinc-900/40 text-zinc-100"
            }`}
          >
            <div className={`mb-1 text-xs font-medium ${cardTitle}`}>Scheduled tasks</div>
            <p className={`text-2xl font-semibold tabular-nums ${stat}`}>
              {typeof schedulerJobCount === "number" ? schedulerJobCount : "—"}
            </p>
            <p className={`mt-1 text-[11px] ${cardTitle}`}>Registered APScheduler rows</p>
          </div>
          <div
            className={`rounded-lg border p-3 ${
              shellLight ? "border-zinc-200 bg-white text-zinc-900" : "border-zinc-700/80 bg-zinc-900/40 text-zinc-100"
            }`}
          >
            <div className={`mb-1 text-xs font-medium ${cardTitle}`}>Channel activity</div>
            <p className={`text-2xl font-semibold tabular-nums ${stat}`}>
              {typeof channelEventsCount === "number" ? channelEventsCount : "—"}
            </p>
            <p className={`mt-1 text-[11px] ${cardTitle}`}>Recent bus events (tail)</p>
          </div>
          <div
            className={`rounded-lg border p-3 ${
              shellLight ? "border-zinc-200 bg-white text-zinc-900" : "border-zinc-700/80 bg-zinc-900/40 text-zinc-100"
            }`}
          >
            <div className={`mb-1 text-xs font-medium ${cardTitle}`}>Autonomy mode</div>
            <p className={`text-sm font-semibold ${stat}`}>{autonomous ? "On" : "Off"}</p>
            <p className={`mt-1 text-[11px] ${cardTitle}`}>NEXA_AUTONOMOUS_MODE</p>
          </div>
        </div>
    </section>
  );
}
