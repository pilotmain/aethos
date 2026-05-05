"use client";

import { Package, ShieldCheck, ShieldOff } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { formatMissionControlApiError, webFetch } from "@/lib/api";
import { isConfigured } from "@/lib/config";

type CatalogEntry = {
  id?: string;
  name?: string;
  version?: string;
  description?: string;
  risk_level?: string;
  trust_score?: number;
  install_preview_ok?: boolean;
  install_preview_errors?: string[];
};

type CatalogResponse = { ok?: boolean; catalog?: CatalogEntry[] };

/** AethOS Forge soft launch — read-only catalog + safe preview flags (Phase 55). */
export function AethosForgePanel(props: { shellLight: boolean }) {
  const { shellLight } = props;
  const [data, setData] = useState<CatalogEntry[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!isConfigured()) return;
    setLoading(true);
    setErr(null);
    try {
      const r = await webFetch<CatalogResponse>("/skills/marketplace/catalog");
      setData(r.catalog || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!isConfigured()) return null;

  const title = shellLight ? "text-zinc-900" : "text-zinc-100";
  const muted = shellLight ? "text-zinc-500" : "text-zinc-500";
  const border = shellLight ? "border-zinc-200/90" : "border-zinc-800/60";
  const bg = shellLight ? "bg-white/95" : "bg-zinc-950/40";

  return (
    <section className={`rounded-xl border p-4 ${border} ${bg}`}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Package className={`h-4 w-4 ${shellLight ? "text-zinc-600" : "text-zinc-400"}`} aria-hidden />
          <h2 className={`text-sm font-semibold ${title}`}>AethOS Forge (preview)</h2>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className={`rounded-md border px-2 py-1 text-xs ${
            shellLight
              ? "border-zinc-300 bg-zinc-50 text-zinc-800 hover:bg-zinc-100"
              : "border-zinc-600 bg-zinc-900 text-zinc-200 hover:bg-zinc-800"
          }`}
        >
          Refresh
        </button>
      </div>
      <p className={`mb-3 text-[11px] ${muted}`}>
        Catalog ships as <code className="rounded bg-black/10 px-1">data/aethos_marketplace/catalog.json</code>.
        Install flows remain guarded — preview shows validation only.
      </p>
      {err ? (
        <p className="text-xs text-rose-600 dark:text-rose-400">{formatMissionControlApiError(err)}</p>
      ) : null}
      {loading && !data?.length ? (
        <p className={`text-xs ${muted}`}>Loading catalog…</p>
      ) : null}
      {!loading && data && data.length === 0 ? (
        <p className={`text-xs ${muted}`}>Catalog is empty.</p>
      ) : null}
      <ul className="space-y-2">
        {(data || []).map((row) => (
          <li
            key={String(row.id || row.name)}
            className={`rounded-lg border px-3 py-2 text-xs ${shellLight ? "border-zinc-200 bg-zinc-50/80" : "border-zinc-800 bg-black/20"}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <span className={`font-medium ${title}`}>{row.name || row.id || "Skill"}</span>
                {row.version ? (
                  <span className={`ml-2 ${muted}`}>v{row.version}</span>
                ) : null}
              </div>
              <span className="flex items-center gap-1 shrink-0">
                {row.install_preview_ok ? (
                  <>
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" aria-hidden />
                    <span className="text-emerald-700 dark:text-emerald-400">Safe preview</span>
                  </>
                ) : (
                  <>
                    <ShieldOff className="h-3.5 w-3.5 text-amber-600" aria-hidden />
                    <span className="text-amber-800 dark:text-amber-300">Blocked</span>
                  </>
                )}
              </span>
            </div>
            {row.description ? <p className={`mt-1 ${muted}`}>{row.description}</p> : null}
            {(row.install_preview_errors || []).length ? (
              <p className={`mt-1 font-mono text-[10px] ${muted}`}>
                {(row.install_preview_errors || []).join("; ")}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
