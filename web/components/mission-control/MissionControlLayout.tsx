"use client";

import Link from "next/link";
import { Activity, Menu, Radio, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ArtifactsPanel } from "@/components/mission-control/ArtifactsPanel";
import { CreateAgentPanel } from "@/components/mission-control/CreateAgentPanel";
import { MissionBuilderPanel } from "@/components/mission-control/MissionBuilderPanel";
import { MissionControlLiveEvents } from "@/components/mission-control/MissionControlLiveEvents";
import { MissionControlMaintenanceControls } from "@/components/mission-control/MissionControlMaintenanceControls";
import { MissionGraph } from "@/components/mission-control/MissionGraph";
import type { IntegrityAlertRow } from "@/components/mission-control/IntegrityAlertBanner";
import { IntegrityAlertBanner } from "@/components/mission-control/IntegrityAlertBanner";
import { PrivacyTrustPanel } from "@/components/mission-control/PrivacyTrustPanel";
import { OfflineModeBanner } from "@/components/mission-control/OfflineModeBanner";
import { PrivacyIndicatorBadge } from "@/components/mission-control/PrivacyIndicatorBadge";
import { DevOpsPanel, type DevRunRow } from "@/components/mission-control/DevOpsPanel";
import {
  AutonomyIntelligencePanel,
  type AutonomousTaskRow,
  type DecisionRow,
  type FeedbackRow,
  type AutonomyStats,
} from "@/components/mission-control/AutonomyIntelligencePanel";
import { Phase22Overview } from "@/components/mission-control/Phase22Overview";
import { ProductionIntelPanel } from "@/components/mission-control/ProductionIntelPanel";
import { ProviderTransparencyPanel } from "@/components/mission-control/ProviderTransparencyPanel";
import { TokenEconomyPanel } from "@/components/mission-control/TokenEconomyPanel";
import type { UiTheme } from "@/components/settings/UserSettingsPanel";
import { UserSettingsPanel } from "@/components/settings/UserSettingsPanel";
import { formatMissionControlApiError, webFetch } from "@/lib/api";
import { isConfigured, readConfig } from "@/lib/config";
import { useMissionControlSnapshot } from "@/lib/mission-control/useMissionControlSnapshot";
import {
  appendMissionLiveEvent,
  refreshMissionControlStore,
} from "@/lib/state/missionControlStore";
import {
  disconnectMissionControlStream,
  ensureMissionControlStream,
  subscribeMissionMessages,
} from "@/lib/ws/missionControlStream";

const CONFIG_KEY = "nexa_web_v1";

/**
 * Phase 12–21 — Mission Control shell + settings sidebar / drawer + theme-aware shell.
 */
export function MissionControlLayout() {
  const [configured, setConfigured] = useState(false);
  const [sessionUserId, setSessionUserId] = useState("");
  const [mcTheme, setMcTheme] = useState<UiTheme>("dark");
  const [mcAutoRefresh, setMcAutoRefresh] = useState(true);
  const [settingsDrawerOpen, setSettingsDrawerOpen] = useState(false);
  const pollMs = mcAutoRefresh ? 10000 : 0;

  const { data: snap, loading: snapLoading, error: snapErr, refresh: refreshMc } =
    useMissionControlSnapshot(pollMs);

  const onPrefsApplied = useCallback((prefs: { theme: UiTheme; auto_refresh: boolean }) => {
    setMcTheme(prefs.theme);
    setMcAutoRefresh(prefs.auto_refresh);
  }, []);

  useEffect(() => {
    setConfigured(isConfigured());
  }, []);

  useEffect(() => {
    const syncUser = () => setSessionUserId(readConfig().userId.trim());
    syncUser();
    const onStorage = (e: StorageEvent) => {
      if (e.key === CONFIG_KEY) syncUser();
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener("focus", syncUser);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("focus", syncUser);
    };
  }, []);

  useEffect(() => {
    if (mcTheme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
    return () => {
      document.documentElement.classList.remove("dark");
    };
  }, [mcTheme]);

  useEffect(() => {
    if (!configured || !sessionUserId) return;
    void refreshMc();
  }, [sessionUserId, configured, refreshMc]);

  /** Single-stream bootstrap: one WS + coordinated HTTP refresh (Phase 14). */
  useEffect(() => {
    if (!isConfigured()) return;
    void refreshMissionControlStore();
    ensureMissionControlStream();
    let debounce: number | undefined;
    const unsub = subscribeMissionMessages((data) => {
      appendMissionLiveEvent(data);
      window.clearTimeout(debounce);
      debounce = window.setTimeout(() => void refreshMissionControlStore(), 400);
    });
    return () => {
      unsub();
      window.clearTimeout(debounce);
      disconnectMissionControlStream();
    };
  }, []);

  const offline = snap?.runtime?.offline_mode;
  const strict = snap?.runtime?.strict_privacy_mode;
  const integrityBannerLevel =
    snap?.runtime?.integrity_banner_level ??
    (snap?.runtime?.integrity_alert_active ? "critical" : null);

  const integrityAlerts = snap?.integrity_alerts as IntegrityAlertRow[] | undefined;

  const privacyScore = snap?.runtime?.privacy_score as number | undefined;
  const userPrivacyMode = snap?.runtime?.user_privacy_mode as string | undefined;

  const dismissWarning = async (alertId: string) => {
    await webFetch("/mission-control/override-alert", {
      method: "POST",
      body: JSON.stringify({ alert_id: alertId, action: "ignore" }),
    });
    await refreshMc();
  };

  const shellLight = mcTheme === "light";

  const outerClass = shellLight
    ? "min-h-screen bg-zinc-100 text-zinc-900 antialiased transition-colors duration-300"
    : "min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-950 to-black text-zinc-100 transition-colors duration-300";

  const headerBorder = shellLight ? "border-zinc-200 bg-white/90" : "border-zinc-800/80 bg-zinc-950/90";
  const headerSub = shellLight ? "text-zinc-600" : "text-zinc-500";
  const linkHome = shellLight ? "text-zinc-600 hover:text-zinc-900" : "text-zinc-400 hover:text-zinc-200";

  return (
    <div className={outerClass}>
      <header className={`sticky top-0 z-30 border-b backdrop-blur ${headerBorder}`}>
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-2">
            <Activity className={`h-5 w-5 shrink-0 ${shellLight ? "text-emerald-600" : "text-emerald-400"}`} aria-hidden />
            <div>
              <h1 className={`text-lg font-semibold tracking-tight ${shellLight ? "text-zinc-900" : "text-zinc-50"}`}>
                Mission Control
              </h1>
              <p className={`text-[11px] ${headerSub}`}>What&apos;s live · activity · your outputs</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            {configured && sessionUserId ? (
              <span
                className={`max-w-[200px] truncate font-mono text-[10px] ${shellLight ? "text-zinc-500" : "text-zinc-500"}`}
                title={sessionUserId}
              >
                User: {sessionUserId.length > 18 ? `${sessionUserId.slice(0, 18)}…` : sessionUserId}
              </span>
            ) : null}
            {!configured ? (
              <span
                className={`rounded-md border px-2 py-1 ${
                  shellLight
                    ? "border-amber-400/50 bg-amber-50 text-amber-950"
                    : "border-amber-500/40 bg-amber-950/40 text-amber-100"
                }`}
              >
                Configure{" "}
                <Link href="/login" className="font-medium underline">
                  Login
                </Link>{" "}
                for authenticated APIs.
              </span>
            ) : (
              <>
                <PrivacyIndicatorBadge indicator={snap?.privacy_indicator} />
                <span
                  className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 ${
                    shellLight
                      ? "border-emerald-300/60 bg-emerald-50 text-emerald-950"
                      : "border-emerald-500/30 bg-emerald-950/30 text-emerald-100"
                  }`}
                >
                  <Radio className="h-3 w-3" aria-hidden />
                  Session ready
                </span>
              </>
            )}
            {configured ? (
              <button
                type="button"
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 lg:hidden ${
                  shellLight
                    ? "border-zinc-300 bg-white text-zinc-800"
                    : "border-zinc-600 bg-zinc-900 text-zinc-100"
                }`}
                onClick={() => setSettingsDrawerOpen(true)}
              >
                <Menu className="h-3.5 w-3.5" aria-hidden />
                Settings
              </button>
            ) : null}
            <Link href="/" className={`underline-offset-4 hover:underline ${linkHome}`}>
              Home
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 px-4 py-6 lg:flex-row lg:items-start">
        <main className="min-w-0 flex-1 space-y-6">
          {snapErr && configured ? (
            <div
              className={`flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2 text-xs ${
                shellLight
                  ? "border-rose-300 bg-rose-50 text-rose-950"
                  : "border-rose-500/35 bg-rose-950/30 text-rose-100"
              }`}
            >
              <p className="min-w-0 flex-1">{formatMissionControlApiError(snapErr)}</p>
              <button
                type="button"
                className={`shrink-0 rounded border px-2 py-1 ${
                  shellLight
                    ? "border-rose-400/60 bg-white text-rose-900 hover:bg-rose-50"
                    : "border-rose-400/50 bg-rose-950/50 text-rose-50 hover:bg-rose-900/60"
                }`}
                onClick={() => void refreshMc()}
              >
                Retry
              </button>
            </div>
          ) : null}
          {configured ? (
            <MissionControlMaintenanceControls
              shellLight={shellLight}
              sqlPurgeEnabled={Boolean(snap?.maintenance?.sql_purge_enabled)}
              onAfterMaintenance={refreshMc}
            />
          ) : null}

          {configured ? (
            <IntegrityAlertBanner
              level={integrityBannerLevel}
              alerts={integrityAlerts}
              onIgnoreAlert={integrityBannerLevel === "warning" ? dismissWarning : undefined}
            />
          ) : null}
          {(offline || strict) && configured ? (
            <OfflineModeBanner offline={offline} strictMode={strict} />
          ) : null}

          {configured ? (
            <PrivacyTrustPanel
              privacyScore={privacyScore}
              userPrivacyMode={userPrivacyMode}
              recentAlerts={integrityAlerts}
              loading={snapLoading && configured}
            />
          ) : null}

          <ProviderTransparencyPanel
            transparency={snap?.provider_transparency}
            metrics={snap?.metrics}
            loading={snapLoading && configured}
          />

          {configured ? (
            <TokenEconomyPanel
              tokenEconomy={snap?.token_economy as Record<string, unknown> | undefined}
              loading={snapLoading && configured}
            />
          ) : null}

          {configured ? (
            <Phase22Overview
              shellLight={shellLight}
              longRunningCount={
                Array.isArray(snap?.long_running_sessions) ? snap!.long_running_sessions!.length : undefined
              }
              schedulerJobCount={
                Array.isArray(snap?.scheduler_jobs) ? snap!.scheduler_jobs!.length : undefined
              }
              channelEventsCount={
                Array.isArray(snap?.channel_activity) ? snap!.channel_activity!.length : undefined
              }
              autonomous={Boolean(snap?.runtime && (snap.runtime as { autonomous_mode?: boolean }).autonomous_mode)}
            />
          ) : null}

          {configured ? (
            <AutonomyIntelligencePanel
              shellLight={shellLight}
              autonomousTasks={snap?.autonomous_tasks as unknown as AutonomousTaskRow[] | undefined}
              autonomyDecisions={snap?.autonomy_decisions as unknown as DecisionRow[] | undefined}
              autonomyFeedback={snap?.autonomy_feedback as unknown as FeedbackRow[] | undefined}
              autonomyExecutionStats={snap?.autonomy_execution_stats as unknown as AutonomyStats | undefined}
              loading={snapLoading && configured}
              onRefresh={() => void refreshMc()}
            />
          ) : null}

          {configured ? (
            <ProductionIntelPanel
              shellLight={shellLight}
              phase46={snap?.phase46 as Record<string, unknown> | undefined}
              loading={snapLoading && configured}
            />
          ) : null}

          {configured ? (
            <DevOpsPanel
              shellLight={shellLight}
              workspaces={snap?.dev_workspaces}
              runs={snap?.dev_runs as unknown as DevRunRow[] | undefined}
              loading={snapLoading && configured}
            />
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2 lg:items-stretch">
            <MissionGraph />
            <MissionControlLiveEvents />
          </div>

          <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
            <MissionBuilderPanel />
            <CreateAgentPanel />
          </div>

          <ArtifactsPanel />
        </main>

        <aside className="hidden w-full max-w-sm shrink-0 lg:block lg:w-80 lg:max-w-none">
          <UserSettingsPanel onPreferencesApplied={onPrefsApplied} />
        </aside>
      </div>

      {settingsDrawerOpen ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
            aria-label="Close settings"
            onClick={() => setSettingsDrawerOpen(false)}
          />
          <div className="fixed inset-y-0 right-0 z-50 flex w-[min(100vw,22rem)] flex-col border-l border-zinc-800 bg-zinc-950 shadow-2xl transition-transform duration-200 ease-out lg:hidden">
            <div className="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
              <span className="text-sm font-medium text-zinc-200">Settings</span>
              <button
                type="button"
                className="rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
                onClick={() => setSettingsDrawerOpen(false)}
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              <UserSettingsPanel compact onPreferencesApplied={onPrefsApplied} />
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
