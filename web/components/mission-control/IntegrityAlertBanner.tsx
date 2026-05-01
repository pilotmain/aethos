"use client";

import { ShieldAlert } from "lucide-react";

export type IntegrityBannerLevel = "critical" | "warning" | null | undefined;

/** Phase 18 — critical blocks; warnings surface without implying hard failure. */
export function IntegrityAlertBanner({ level }: { level?: IntegrityBannerLevel }) {
  if (!level) return null;

  if (level === "critical") {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-rose-500/40 bg-rose-950/40 px-3 py-2 text-xs text-rose-100">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-300" aria-hidden />
        <div>
          <span className="font-semibold">Security integrity alert</span>
          <span className="text-rose-200/90">
            {" "}
            Post-provider screening flagged high-confidence secret-shaped material or a critical integrity event. Review
            Mission Control events and integrity alerts.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-950/35 px-3 py-2 text-xs text-amber-100">
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden />
      <div>
        <span className="font-semibold">Integrity warning</span>
        <span className="text-amber-200/90">
          {" "}
          Sensitive patterns (for example PII) were flagged in screened output. You can continue; review Mission Control
          when convenient.
        </span>
      </div>
    </div>
  );
}
