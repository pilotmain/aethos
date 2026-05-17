"use client";

import { useCallback, useState } from "react";
import { Loader2, Wrench } from "lucide-react";
import { MaintenancePanel } from "@/components/mission-control/MaintenancePanel";
import { webFetch } from "@/lib/api";
import { isConfigured } from "@/lib/config";
import { refreshMissionControlStore } from "@/lib/state/missionControlStore";

export type MissionControlMaintenanceControlsProps = {
  shellLight: boolean;
  sqlPurgeEnabled: boolean;
  onAfterMaintenance: () => Promise<void>;
};

/**
 * AethOS maintenance entry point (reset / purge / dev SQL erase) without legacy dashboard UI.
 */
export function MissionControlMaintenanceControls({
  shellLight,
  sqlPurgeEnabled,
  onAfterMaintenance,
}: MissionControlMaintenanceControlsProps) {
  const [open, setOpen] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);
  const [purgeBusy, setPurgeBusy] = useState(false);
  const [sqlHardBusy, setSqlHardBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refreshAfter = useCallback(async () => {
    await refreshMissionControlStore();
    await onAfterMaintenance();
  }, [onAfterMaintenance]);

  const performResetVisible = async (opts: { includeCustomAgents: boolean }) => {
    setErr(null);
    setResetBusy(true);
    setNotice(null);
    try {
      await webFetch(`/mission-control/reset`, {
        method: "POST",
        body: JSON.stringify({
          include_custom_agents: opts.includeCustomAgents,
          hard_delete: false,
        }),
      });
      setNotice("Mission Control reset.");
      await refreshAfter();
    } catch (e) {
      const msg = (e as Error).message;
      setErr(msg);
      throw e;
    } finally {
      setResetBusy(false);
    }
  };

  const performPurgeEverything = async () => {
    setErr(null);
    setPurgeBusy(true);
    setNotice(null);
    try {
      await webFetch(`/mission-control/purge`, {
        method: "POST",
        body: JSON.stringify({ hard_delete: false }),
      });
      setNotice("Mission Control fully cleared (all custom agents disabled).");
      await refreshAfter();
    } catch (e) {
      const msg = (e as Error).message;
      setErr(msg);
      throw e;
    } finally {
      setPurgeBusy(false);
    }
  };

  const performHardSqlErase = async () => {
    setErr(null);
    setSqlHardBusy(true);
    setNotice(null);
    try {
      await webFetch(`/mission-control/reset-hard`, {
        method: "POST",
        body: JSON.stringify({
          include_audit_logs: false,
          include_pending_permissions: true,
          include_custom_agents: true,
          clear_workspace_files: true,
        }),
      });
      setNotice("Database hard erase completed (SQL purge).");
      await refreshAfter();
    } catch (e) {
      const msg = (e as Error).message;
      setErr(msg);
      throw e;
    } finally {
      setSqlHardBusy(false);
    }
  };

  if (!isConfigured()) return null;

  const btnShell = shellLight
    ? "border-zinc-300 bg-white text-zinc-800 hover:border-zinc-400"
    : "border-zinc-600 bg-zinc-900/80 text-zinc-400 hover:border-violet-500/40 hover:text-zinc-200";

  const busy = resetBusy || purgeBusy || sqlHardBusy;

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={busy}
        className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium disabled:opacity-50 ${btnShell}`}
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <Wrench className="h-3.5 w-3.5 opacity-80" aria-hidden />}
        Maintenance
      </button>
      {(notice || err) && (
        <div className="min-w-0 flex-1 text-xs" aria-live="polite">
          {notice ? (
            <p
              className={
                shellLight
                  ? "rounded-md border border-emerald-300/60 bg-emerald-50 px-2 py-1 text-emerald-950"
                  : "rounded-md border border-emerald-500/25 bg-emerald-500/10 px-2 py-1 text-emerald-100/90"
              }
            >
              {notice}
            </p>
          ) : null}
          {err ? (
            <p
              className={
                shellLight
                  ? "mt-1 rounded-md border border-rose-300/70 bg-rose-50 px-2 py-1 text-rose-950"
                  : "mt-1 rounded-md border border-rose-500/30 bg-rose-500/10 px-2 py-1 text-rose-100/90"
              }
            >
              {err}
            </p>
          ) : null}
        </div>
      )}

      <MaintenancePanel
        open={open}
        onOpenChange={setOpen}
        sqlPurgeEnabled={sqlPurgeEnabled}
        busyReset={resetBusy}
        busyPurge={purgeBusy}
        busyHardSql={sqlHardBusy}
        onResetVisible={performResetVisible}
        onHardErase={performHardSqlErase}
        onDeleteEverything={performPurgeEverything}
      />
    </div>
  );
}
