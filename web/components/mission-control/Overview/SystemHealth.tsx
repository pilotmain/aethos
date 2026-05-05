"use client";

import type { SystemHealthFlags } from "@/types/mission-control";

export type SystemHealthProps = {
  health: SystemHealthFlags;
};

function Row({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-zinc-800/80 py-2 text-sm last:border-0">
      <span className="text-zinc-400">{label}</span>
      <span className={ok ? "text-emerald-400" : "text-zinc-500"}>{ok ? "OK" : "Check"}</span>
    </div>
  );
}

export function SystemHealth({ health }: SystemHealthProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-4">
      <h3 className="mb-2 text-sm font-semibold text-zinc-200">Services</h3>
      <Row label="HTTP API (/health)" ok={health.api} />
      <Row label="Scheduler jobs (enabled)" ok={health.cron} />
      <Row label="Remote providers available" ok={health.providers} />
      <p className="mt-3 text-[11px] leading-relaxed text-zinc-600">
        Cron/providers are inferred from Mission Control state (scheduler_jobs + runtime hints). Configure providers in
        the API environment if rows show “Check”.
      </p>
    </div>
  );
}
