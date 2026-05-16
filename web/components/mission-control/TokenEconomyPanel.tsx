"use client";

import { Coins, Loader2 } from "lucide-react";

/**
 * Phase 38 — token / cost roll-ups from Mission Control snapshot (no raw payloads).
 */
export function TokenEconomyPanel({
  tokenEconomy,
  loading,
}: {
  tokenEconomy?: Record<string, unknown> | null;
  loading?: boolean;
}) {
  const te = tokenEconomy ?? {};
  const tokens = typeof te.tokens_sent_today === "number" ? te.tokens_sent_today : null;
  const cost = typeof te.cost_estimate_usd_today === "number" ? te.cost_estimate_usd_today : null;
  const blocks = typeof te.budget_blocks_today === "number" ? te.budget_blocks_today : null;
  const local = typeof te.local_calls_today === "number" ? te.local_calls_today : null;
  const ext = typeof te.external_calls_today === "number" ? te.external_calls_today : null;
  const lastSummary = te.last_payload_summary as Record<string, unknown> | undefined;
  const redactCount =
    typeof te.last_redactions_count === "number" ? te.last_redactions_count : null;

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950/70 px-4 py-4 transition-colors duration-300">
      <div className="mb-2 flex items-center gap-2">
        <Coins className="h-4 w-4 text-amber-400" aria-hidden />
        <h2 className="text-sm font-medium text-zinc-200">Token economy</h2>
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500" /> : null}
      </div>
      <p className="mb-3 text-xs text-zinc-500">
        Estimated outbound tokens and cost for this session — every provider call is budget-checked before leaving AethOS.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-zinc-800/90 bg-black/30 p-3 text-[11px]">
          <div className="mb-2 font-medium text-zinc-400">Today (estimate)</div>
          <ul className="space-y-1 text-zinc-300">
            <li>
              Tokens:{" "}
              <span className="font-mono text-amber-200/90">{tokens !== null ? tokens : "—"}</span>
            </li>
            <li>
              Cost (USD est.):{" "}
              <span className="font-mono text-emerald-200/90">{cost !== null ? cost.toFixed(4) : "—"}</span>
            </li>
            <li>
              Budget blocks:{" "}
              <span className="font-mono text-rose-200/90">{blocks !== null ? blocks : "—"}</span>
            </li>
          </ul>
        </div>
        <div className="rounded-lg border border-zinc-800/90 bg-black/30 p-3 text-[11px]">
          <div className="mb-2 font-medium text-zinc-400">Calls</div>
          <ul className="space-y-1 text-zinc-300">
            <li>
              Local stub: <span className="font-mono text-zinc-200">{local !== null ? local : "—"}</span>
            </li>
            <li>
              External: <span className="font-mono text-zinc-200">{ext !== null ? ext : "—"}</span>
            </li>
            <li>
              Last redaction rows:{" "}
              <span className="font-mono text-zinc-200">{redactCount !== null ? redactCount : "—"}</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-zinc-800/90 bg-black/20 p-3 text-[11px] text-zinc-400">
        <div className="mb-1 font-medium text-zinc-500">Last payload summary</div>
        {lastSummary && Object.keys(lastSummary).length > 0 ? (
          <pre className="overflow-x-auto whitespace-pre-wrap break-all font-mono text-[10px] text-zinc-300">
            {JSON.stringify(lastSummary, null, 2)}
          </pre>
        ) : (
          <p className="text-zinc-600">No outbound provider calls recorded yet for this user.</p>
        )}
      </div>
    </section>
  );
}
