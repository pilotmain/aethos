"use client";

import { ShieldAlert } from "lucide-react";

/** Phase 17 — surfaced when ``runtime.integrity_alert_active`` from Mission Control state. */
export function IntegrityAlertBanner({ active }: { active?: boolean }) {
  if (!active) return null;
  return (
    <div className="flex items-start gap-2 rounded-lg border border-rose-500/40 bg-rose-950/40 px-3 py-2 text-xs text-rose-100">
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-300" aria-hidden />
      <div>
        <span className="font-semibold">Security integrity alert</span>
        <span className="text-rose-200/90">
          {" "}
          Post-provider screening flagged sensitive patterns or a critical integrity event was logged. Review Mission
          Control events and integrity alerts.
        </span>
      </div>
    </div>
  );
}
