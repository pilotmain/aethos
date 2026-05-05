"use client";

import { Copy } from "lucide-react";
import type { ChannelStatus } from "@/lib/aethos-types";

function healthBadgeClass(h: ChannelStatus["health"]): string {
  if (h === "ok") return "border-emerald-500/40 bg-emerald-500/15 text-emerald-100";
  if (h === "missing_config") return "border-amber-500/40 bg-amber-500/15 text-amber-100";
  if (h === "disabled") return "border-zinc-600 bg-zinc-800/80 text-zinc-400";
  return "border-zinc-600 bg-zinc-800/80 text-zinc-400";
}

function CopyUrl({
  label,
  url,
  onCopied,
}: {
  label: string;
  url: string;
  onCopied?: () => void;
}) {
  return (
    <div className="flex flex-wrap items-start gap-1.5 text-[10px]">
      <span className="shrink-0 text-zinc-500">{label}</span>
      <code className="min-w-0 flex-1 break-all text-zinc-400">{url}</code>
      <button
        type="button"
        title={`Copy ${label}`}
        className="shrink-0 rounded border border-white/10 px-1 py-px text-zinc-400 hover:border-white/25 hover:text-zinc-200"
        onClick={() =>
          void navigator.clipboard.writeText(url).then(() => {
            onCopied?.();
          })
        }
      >
        <Copy className="h-3 w-3" aria-hidden />
      </button>
    </div>
  );
}

export function ChannelAdminPanel({
  data,
  error,
  onCopied,
}: {
  data: { channels: ChannelStatus[] } | null;
  error: string | null;
  onCopied?: () => void;
}) {
  if (error) {
    return <p className="text-[10px] text-rose-300/85">{error}</p>;
  }
  if (!data) {
    return <p className="text-[10px] text-zinc-500">Loading channels…</p>;
  }

  return (
    <div className="space-y-2">
      {data.channels.map((ch) => (
        <div
          key={ch.channel}
          className="rounded border border-white/10 bg-white/[0.02] px-2 py-2 text-[10px] text-zinc-300"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-zinc-200">{ch.label}</span>
            <span
              className={`rounded border px-1.5 py-px text-[9px] uppercase tracking-wide ${healthBadgeClass(ch.health)}`}
            >
              {ch.health.replace(/_/g, " ")}
            </span>
          </div>
          <p className="mt-1 text-zinc-500">
            {ch.configured ? (
              <span className="text-emerald-400/90">Configured</span>
            ) : (
              <span className="text-amber-400/90">Missing configuration</span>
            )}
            {" · "}
            {ch.enabled ? (
              <span className="text-zinc-400">Enabled</span>
            ) : (
              <span className="text-zinc-500">Not enabled</span>
            )}
          </p>
          {ch.missing.length > 0 && (
            <div className="mt-1.5">
              <p className="text-[9px] font-medium uppercase tracking-wide text-zinc-500">Missing env</p>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-3.5 text-zinc-400">
                {ch.missing.map((m) => (
                  <li key={m} className="font-mono">
                    {m}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(ch.governance_enabled != null ||
            (ch.allowed_roles != null && ch.allowed_roles.length > 0) ||
            ch.approval_required != null) && (
            <p className="mt-1 text-zinc-500">
              <span className="text-zinc-600">Governance:</span>{" "}
              {ch.governance_enabled != null ? (ch.governance_enabled ? "channel on" : "channel off") : "—"} · roles{" "}
              {(ch.allowed_roles ?? []).join(", ") || "—"} · approval {String(ch.approval_required ?? false)}
            </p>
          )}
          {ch.health_details && Object.keys(ch.health_details).length > 0 && (
            <div className="mt-1.5 rounded border border-white/5 bg-black/20 px-1.5 py-1 font-mono text-[9px] leading-snug text-zinc-500">
              {Object.entries(ch.health_details).map(([k, v]) => (
                <div key={k}>
                  <span className="text-zinc-600">{k}:</span> {v}
                </div>
              ))}
            </div>
          )}
          {ch.webhook_url && <CopyUrl label="Primary webhook" url={ch.webhook_url} onCopied={onCopied} />}
          {ch.webhook_urls &&
            Object.entries(ch.webhook_urls).map(([k, u]) =>
              u ? <CopyUrl key={k} label={k} url={u} onCopied={onCopied} /> : null,
            )}
          {ch.notes && ch.notes.length > 0 && (
            <ul className="mt-1.5 list-disc space-y-0.5 pl-3.5 text-zinc-500">
              {ch.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
