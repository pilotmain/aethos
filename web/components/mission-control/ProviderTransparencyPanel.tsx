"use client";

import { Eye, Loader2 } from "lucide-react";

export function ProviderTransparencyPanel({
  transparency,
  metrics,
  loading,
}: {
  transparency?: Record<string, unknown> | null;
  metrics?: Record<string, unknown> | null;
  loading?: boolean;
}) {
  const by = (transparency?.by_provider ?? {}) as Record<
    string,
    { calls?: number; blocked?: number; fallback?: number; completed?: number }
  >;
  const providers = Object.keys(by).sort();
  const red = transparency?.privacy_redactions_observed;
  const blk = transparency?.privacy_blocks_observed;

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950/70 px-4 py-4 transition-colors duration-300">
      <div className="mb-2 flex items-center gap-2">
        <Eye className="h-4 w-4 text-cyan-400" aria-hidden />
        <h2 className="text-sm font-medium text-zinc-200">Provider transparency</h2>
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500" /> : null}
      </div>
      <p className="mb-3 text-xs text-zinc-500">
        Live signals from the provider gateway and privacy firewall — Nexa = OpenClaw-class control + guaranteed PII protection.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-zinc-800/90 bg-black/30 p-3 text-[11px]">
          <div className="mb-2 font-medium text-zinc-400">Privacy actions (session)</div>
          <ul className="space-y-1 text-zinc-300">
            <li>
              Redactions: <span className="font-mono text-amber-200/90">{typeof red === "number" ? red : "—"}</span>
            </li>
            <li>
              Blocks: <span className="font-mono text-rose-200/90">{typeof blk === "number" ? blk : "—"}</span>
            </li>
          </ul>
        </div>
        <div className="rounded-lg border border-zinc-800/90 bg-black/30 p-3 text-[11px]">
          <div className="mb-2 font-medium text-zinc-400">Mission reliability</div>
          <ul className="space-y-1 text-zinc-300">
            <li>
              Success rate:{" "}
              <span className="font-mono text-emerald-200/90">
                {metrics && typeof metrics.success_rate === "number"
                  ? `${(metrics.success_rate * 100).toFixed(1)}%`
                  : "—"}
              </span>
            </li>
            <li>
              Avg task runtime:{" "}
              <span className="font-mono text-zinc-200">
                {metrics && typeof metrics.avg_runtime_ms === "number" ? `${metrics.avg_runtime_ms} ms` : "—"}
              </span>
            </li>
            <li>
              Blocked outbound (DB):{" "}
              <span className="font-mono text-zinc-200">
                {metrics && typeof metrics.blocked_calls === "number" ? metrics.blocked_calls : "—"}
              </span>
            </li>
          </ul>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-zinc-500">By provider</div>
        {providers.length === 0 ? (
          <p className="text-xs text-zinc-600">No provider calls recorded yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="w-full min-w-[320px] text-left text-[11px] text-zinc-300">
              <thead className="border-b border-zinc-800 bg-zinc-900/50 text-zinc-500">
                <tr>
                  <th className="px-2 py-1.5 font-medium">Provider</th>
                  <th className="px-2 py-1.5 font-medium">Calls</th>
                  <th className="px-2 py-1.5 font-medium">OK</th>
                  <th className="px-2 py-1.5 font-medium">Blocked</th>
                  <th className="px-2 py-1.5 font-medium">Fallback</th>
                </tr>
              </thead>
              <tbody>
                {providers.map((p) => (
                  <tr key={p} className="border-b border-zinc-800/80 last:border-0">
                    <td className="px-2 py-1.5 font-mono text-cyan-200/90">{p}</td>
                    <td className="px-2 py-1.5">{by[p]?.calls ?? 0}</td>
                    <td className="px-2 py-1.5 text-emerald-300/90">{by[p]?.completed ?? 0}</td>
                    <td className="px-2 py-1.5 text-rose-300/90">{by[p]?.blocked ?? 0}</td>
                    <td className="px-2 py-1.5 text-amber-200/90">{by[p]?.fallback ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
