"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Loader2, Wrench, X } from "lucide-react";
import { ConfirmDangerDialog } from "@/components/mission-control/ConfirmDangerDialog";

export type MaintenancePanelProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sqlPurgeEnabled?: boolean;
  busyReset?: boolean;
  busyPurge?: boolean;
  busyHardSql?: boolean;
  onResetVisible: (opts: { includeCustomAgents: boolean }) => Promise<void>;
  onHardErase: () => Promise<void>;
  onDeleteEverything: () => Promise<void>;
};

export function MaintenancePanel({
  open,
  onOpenChange,
  sqlPurgeEnabled = false,
  busyReset,
  busyPurge,
  busyHardSql,
  onResetVisible,
  onHardErase,
  onDeleteEverything,
}: MaintenancePanelProps) {
  const [includeCustomAgents, setIncludeCustomAgents] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmHard, setConfirmHard] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const busy = !!busyReset || !!busyPurge || !!busyHardSql;

  useEffect(() => {
    if (!open) {
      setIncludeCustomAgents(false);
      setAdvancedOpen(false);
      setConfirmReset(false);
      setConfirmHard(false);
      setConfirmDelete(false);
    }
  }, [open]);

  const closeMaintenanceAfter = async (fn: () => Promise<void>) => {
    await fn();
    onOpenChange(false);
  };

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-[90] flex items-center justify-center p-4">
        <button
          type="button"
          className="absolute inset-0 bg-black/65 backdrop-blur-sm"
          aria-label="Close maintenance"
          onClick={() => !busy && onOpenChange(false)}
        />
        <div className="relative z-10 flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-white/10 bg-[#0c0c10] shadow-2xl">
          <div className="flex items-start justify-between gap-3 border-b border-white/10 px-5 py-4">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 inline-flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-zinc-400">
                <Wrench className="h-4 w-4" aria-hidden />
              </span>
              <div>
                <h2 className="text-lg font-semibold tracking-tight text-zinc-50">
                  Mission Control Maintenance
                </h2>
                <p className="mt-1 text-sm text-zinc-500">
                  Clean up visible state, reports, assignments, and test data.
                </p>
              </div>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => onOpenChange(false)}
              className="rounded-md p-1.5 text-zinc-500 hover:bg-white/5 hover:text-zinc-300 disabled:opacity-40"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="space-y-6 overflow-y-auto px-5 py-5">
            {/* Section 1 — Safe cleanup */}
            <section>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-violet-400/90">
                Recommended
              </p>
              <p className="mb-3 text-sm text-zinc-400">
                Clears visible assignments, reports, dismissed failed jobs, and stale runtime state. Custom agents are
                preserved unless you enable the option below.
              </p>
              <button
                type="button"
                disabled={busy}
                onClick={() => setConfirmReset(true)}
                className="inline-flex w-full items-center justify-center rounded-lg border border-violet-500/35 bg-violet-500/15 px-4 py-2.5 text-sm font-medium text-violet-100 hover:bg-violet-500/25 disabled:opacity-40"
              >
                {busyReset ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Reset visible state
              </button>
            </section>

            {/* Section 2 — Toggle */}
            <section className="rounded-lg border border-white/10 bg-zinc-950/50 px-4 py-3">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-zinc-200">Also disable custom agents</p>
                  <p className="mt-1 text-xs text-zinc-500">
                    Keeps agents by default. Enable this only if you want a fresh agent list when resetting.
                  </p>
                </div>
                <label className="relative inline-flex h-7 w-11 shrink-0 cursor-pointer items-center">
                  <input
                    type="checkbox"
                    className="peer sr-only"
                    checked={includeCustomAgents}
                    disabled={busy}
                    onChange={(e) => setIncludeCustomAgents(e.target.checked)}
                  />
                  <span className="absolute inset-0 rounded-full bg-zinc-700 transition peer-focus-visible:ring-2 peer-focus-visible:ring-violet-500/40 peer-checked:bg-violet-600" />
                  <span className="pointer-events-none absolute left-0.5 top-0.5 h-6 w-6 rounded-full bg-white shadow transition peer-checked:translate-x-[18px]" />
                </label>
              </div>
            </section>

            {/* Section 3 — Advanced */}
            <section className="rounded-lg border border-white/10 bg-zinc-950/40">
              <button
                type="button"
                className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
                onClick={() => setAdvancedOpen((v) => !v)}
                aria-expanded={advancedOpen}
              >
                <div>
                  <p className="text-sm font-medium text-zinc-200">Advanced destructive actions</p>
                  <p className="mt-0.5 text-xs text-zinc-500">Use only in local development. Cannot be undone.</p>
                </div>
                <ChevronDown
                  className={`h-5 w-5 shrink-0 text-zinc-500 transition ${advancedOpen ? "rotate-180" : ""}`}
                  aria-hidden
                />
              </button>
              {advancedOpen ? (
                <div className="space-y-4 border-t border-white/10 px-4 pb-4 pt-3">
                  {sqlPurgeEnabled ? (
                    <div>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => setConfirmHard(true)}
                        className="inline-flex w-full items-center justify-center rounded-lg border border-rose-500/45 bg-transparent px-4 py-2.5 text-sm font-medium text-rose-100 hover:bg-rose-500/10 disabled:opacity-40"
                      >
                        {busyHardSql ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        Hard erase database state
                      </button>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-zinc-700/80 bg-zinc-900/40 px-3 py-3">
                      <p className="text-sm font-medium text-zinc-400">Hard erase unavailable</p>
                      <p className="mt-1 text-xs text-zinc-600">
                        SQL purge is disabled. Enable{" "}
                        <span className="font-mono text-zinc-500">NEXA_MISSION_CONTROL_SQL_PURGE=true</span> in local
                        development to unlock this action.
                      </p>
                    </div>
                  )}
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setConfirmDelete(true)}
                    className="inline-flex w-full items-center justify-center rounded-lg border border-rose-600/50 bg-rose-600/20 px-4 py-2.5 text-sm font-semibold text-rose-50 hover:bg-rose-600/30 disabled:opacity-40"
                  >
                    {busyPurge ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Delete everything
                  </button>
                </div>
              ) : null}
            </section>
          </div>
        </div>
      </div>

      <ConfirmDangerDialog
        open={confirmReset}
        title="Reset visible Mission Control?"
        description="This clears visible assignments, workspace reports, spawn tracking, and related runtime state for your user."
        confirmPhrase="RESET"
        actionLabel="Reset visible state"
        variant="violet"
        onCancel={() => setConfirmReset(false)}
        onConfirm={async () => {
          await closeMaintenanceAfter(() => onResetVisible({ includeCustomAgents }));
        }}
      />

      <ConfirmDangerDialog
        open={confirmHard}
        title="Hard erase database state?"
        description="Permanently deletes Mission Control–related database rows for your user and clears workspace report files per server settings. For development only."
        confirmPhrase="HARD ERASE"
        actionLabel="Hard erase"
        variant="redOutline"
        onCancel={() => setConfirmHard(false)}
        onConfirm={async () => {
          await closeMaintenanceAfter(onHardErase);
        }}
      />

      <ConfirmDangerDialog
        open={confirmDelete}
        title="Delete everything?"
        description="Removes visible assignments, jobs, workspace report state, spawn tracking, attention dismissals, and disables all custom agents. This cannot be undone."
        confirmPhrase="DELETE EVERYTHING"
        actionLabel="Delete everything"
        variant="red"
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async () => {
          await closeMaintenanceAfter(onDeleteEverything);
        }}
      />
    </>
  );
}
