"use client";

import { Fingerprint, Loader2 } from "lucide-react";

type AlertBrief = {
  type?: string;
  severity?: string;
  ignored?: boolean;
  alert_id?: string;
};

/** Phase 19 — privacy score, user mode, and recent integrity signals. */
export function PrivacyTrustPanel({
  privacyScore,
  userPrivacyMode,
  recentAlerts,
  loading,
}: {
  privacyScore?: number | null;
  userPrivacyMode?: string | null;
  recentAlerts?: AlertBrief[] | null;
  loading?: boolean;
}) {
  const score =
    typeof privacyScore === "number" && Number.isFinite(privacyScore)
      ? Math.max(0, Math.min(100, Math.round(privacyScore)))
      : null;
  const mode = (userPrivacyMode || "standard").toLowerCase();
  const tail = Array.isArray(recentAlerts) ? recentAlerts.slice(-6).reverse() : [];

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950/70 px-4 py-4">
      <div className="mb-2 flex items-center gap-2">
        <Fingerprint className="h-4 w-4 text-violet-400" aria-hidden />
        <h2 className="text-sm font-medium text-zinc-200">Privacy &amp; trust</h2>
        {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500" /> : null}
      </div>
      <p className="mb-3 text-xs text-zinc-500">
        Session snapshot: how aggressively Nexa filters outbound content and what mode you chose (
        <span className="font-mono text-zinc-400">{mode}</span>
        ).
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-zinc-800/90 bg-black/30 p-3 text-[11px]">
          <div className="mb-2 font-medium text-zinc-400">Privacy score</div>
          <div className="font-mono text-2xl text-violet-200/95">{score !== null ? score : "—"}</div>
          <p className="mt-1 text-zinc-500">Heuristic 0–100 (blocks &amp; alerts reduce; acknowledged warnings recover).</p>
        </div>
        <div className="rounded-lg border border-zinc-800/90 bg-black/30 p-3 text-[11px]">
          <div className="mb-2 font-medium text-zinc-400">User privacy mode</div>
          <ul className="space-y-1 text-zinc-300">
            <li>
              <span className="font-mono text-emerald-200/90">standard</span> — balanced egress screening
            </li>
            <li>
              <span className="font-mono text-amber-200/90">strict</span> — treat medium-confidence secrets as blocking
            </li>
            <li>
              <span className="font-mono text-rose-200/90">paranoid</span> — local_stub only; block outbound PII; block PII
              in model output
            </li>
          </ul>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-zinc-500">Recent integrity alerts</div>
        {tail.length === 0 ? (
          <p className="text-xs text-zinc-600">None in this session snapshot.</p>
        ) : (
          <ul className="max-h-40 space-y-1 overflow-y-auto text-[11px] text-zinc-400">
            {tail.map((a, i) => (
              <li key={`${a.alert_id ?? i}-${i}`} className="flex flex-wrap gap-x-2 border-b border-zinc-800/60 py-1 last:border-0">
                <span className="font-mono text-zinc-500">{String(a.type ?? "alert")}</span>
                <span
                  className={
                    String(a.severity).toLowerCase() === "critical" ? "text-rose-300/90" : "text-amber-200/90"
                  }
                >
                  {a.severity ?? "—"}
                </span>
                {a.ignored ? <span className="text-zinc-600">(dismissed)</span> : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
