"use client";

import { ChevronDown, ChevronRight, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";

export type IntegrityBannerLevel = "critical" | "warning" | null | undefined;

type ExplainShape = {
  reason?: string;
  matched_pattern?: string;
  pattern?: string;
  confidence?: string;
};

export type IntegrityAlertRow = {
  alert_id?: string;
  severity?: string;
  ignored?: boolean;
  type?: string;
  explanation?: ExplainShape;
};

/** Phase 18–19 — severity styling + expandable detection rationale + warning dismiss. */
export function IntegrityAlertBanner({
  level,
  alerts,
  onIgnoreAlert,
}: {
  level?: IntegrityBannerLevel;
  alerts?: IntegrityAlertRow[];
  onIgnoreAlert?: (alertId: string) => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);

  const primary = useMemo(() => {
    const rows = Array.isArray(alerts) ? alerts : [];
    return (
      rows.find(
        (a) =>
          a &&
          !a.ignored &&
          typeof a.explanation === "object" &&
          a.explanation &&
          (a.explanation.reason || a.explanation.matched_pattern || a.explanation.pattern),
      ) ?? rows.find((a) => a && !a.ignored)
    );
  }, [alerts]);

  const explanation = primary?.explanation;
  const pattern =
    (explanation?.matched_pattern || explanation?.pattern || "").trim() || "—";
  const reason = (explanation?.reason || "").trim();
  const conf = (explanation?.confidence || "").trim();
  const aid = typeof primary?.alert_id === "string" ? primary.alert_id : "";
  const canIgnore =
    typeof onIgnoreAlert === "function" &&
    aid &&
    String(primary?.severity || "").toLowerCase() === "warning" &&
    !primary?.ignored;

  if (!level) return null;

  const shell =
    level === "critical"
      ? {
          border: "border-rose-500/40 bg-rose-950/40 text-rose-100",
          icon: "text-rose-300",
          title: "Security integrity alert",
          subtitle:
            "Post-provider screening flagged high-confidence secret-shaped material or a critical integrity event.",
        }
      : {
          border: "border-amber-500/40 bg-amber-950/35 text-amber-100",
          icon: "text-amber-300",
          title: "Integrity warning",
          subtitle:
            "Sensitive patterns (for example PII) were flagged in screened output. You can continue; review details below.",
        };

  return (
    <div className={`rounded-lg border px-3 py-2 text-xs ${shell.border}`}>
      <div className="flex items-start gap-2">
        <ShieldAlert className={`mt-0.5 h-4 w-4 shrink-0 ${shell.icon}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <span className="font-semibold">{shell.title}</span>
          <span className={level === "critical" ? "text-rose-200/90" : "text-amber-200/90"}>
            {" "}
            {shell.subtitle}
          </span>

          {(reason || primary) && (
            <button
              type="button"
              className="mt-2 flex items-center gap-1 text-left text-[11px] text-zinc-400 underline-offset-2 hover:text-zinc-200 hover:underline"
              onClick={() => setOpen((v) => !v)}
            >
              {open ? (
                <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 shrink-0" aria-hidden />
              )}
              Why was this flagged?
            </button>
          )}

          {open ? (
            <div className="mt-2 space-y-1 rounded-md border border-zinc-800/80 bg-black/40 px-2 py-2 text-[11px] text-zinc-300">
              {reason ? (
                <p>
                  <span className="font-medium text-zinc-400">Reason: </span>
                  {reason}
                </p>
              ) : null}
              <p>
                <span className="font-medium text-zinc-400">Matched pattern summary: </span>
                <span className="break-all font-mono text-zinc-200">{pattern}</span>
              </p>
              {conf ? (
                <p>
                  <span className="font-medium text-zinc-400">Confidence: </span>
                  <span className="font-mono">{conf}</span>
                </p>
              ) : null}
              {canIgnore ? (
                <div className="pt-1">
                  <button
                    type="button"
                    className="rounded border border-amber-600/50 bg-amber-950/40 px-2 py-1 text-amber-100 hover:bg-amber-900/50"
                    onClick={() => void onIgnoreAlert!(aid)}
                  >
                    Acknowledge &amp; dismiss warning
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
