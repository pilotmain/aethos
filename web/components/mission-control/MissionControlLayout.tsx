"use client";

import Link from "next/link";
import { Activity, Radio } from "lucide-react";
import { useEffect, useState } from "react";
import { ArtifactsPanel } from "@/components/mission-control/ArtifactsPanel";
import { CreateAgentPanel } from "@/components/mission-control/CreateAgentPanel";
import { MissionBuilderPanel } from "@/components/mission-control/MissionBuilderPanel";
import { MissionControlLiveEvents } from "@/components/mission-control/MissionControlLiveEvents";
import { MissionControlPage } from "@/components/mission-control/MissionControlPage";
import { MissionGraph } from "@/components/mission-control/MissionGraph";
import { IntegrityAlertBanner } from "@/components/mission-control/IntegrityAlertBanner";
import { OfflineModeBanner } from "@/components/mission-control/OfflineModeBanner";
import { PrivacyIndicatorBadge } from "@/components/mission-control/PrivacyIndicatorBadge";
import { ProviderTransparencyPanel } from "@/components/mission-control/ProviderTransparencyPanel";
import { isConfigured } from "@/lib/config";
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

/**
 * Phase 12–13 — Mission Control shell: privacy-first indicators, graph, replay, artifacts, dashboard.
 */
export function MissionControlLayout() {
  const [configured, setConfigured] = useState(false);
  const { data: snap, loading: snapLoading, error: snapErr } = useMissionControlSnapshot(10000);

  useEffect(() => {
    setConfigured(isConfigured());
  }, []);

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
  const integrityAlert = snap?.runtime?.integrity_alert_active;

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-950 to-black text-zinc-100">
      <header className="sticky top-0 z-10 border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 shrink-0 text-emerald-400" aria-hidden />
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-zinc-50">Mission Control</h1>
              <p className="text-[11px] text-zinc-500">Multi-agent graph · live stream · artifacts</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            {!configured ? (
              <span className="rounded-md border border-amber-500/40 bg-amber-950/40 px-2 py-1 text-amber-100">
                Configure{" "}
                <Link href="/login" className="font-medium underline">
                  Login
                </Link>{" "}
                for authenticated APIs.
              </span>
            ) : (
              <>
                <PrivacyIndicatorBadge indicator={snap?.privacy_indicator} />
                <span className="inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-950/30 px-2 py-1 text-emerald-100">
                  <Radio className="h-3 w-3" aria-hidden />
                  Session ready
                </span>
              </>
            )}
            <Link href="/" className="text-zinc-400 underline-offset-4 hover:text-zinc-200 hover:underline">
              Home
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] space-y-6 px-4 py-6">
        {snapErr && configured ? (
          <p className="rounded-lg border border-rose-500/35 bg-rose-950/30 px-3 py-2 text-xs text-rose-100">{snapErr}</p>
        ) : null}
        {configured ? <IntegrityAlertBanner active={integrityAlert} /> : null}
        {(offline || strict) && configured ? (
          <OfflineModeBanner offline={offline} strictMode={strict} />
        ) : null}

        <ProviderTransparencyPanel
          transparency={snap?.provider_transparency}
          metrics={snap?.metrics}
          loading={snapLoading && configured}
        />

        {/* Primary split: agents left, events right */}
        <div className="grid gap-4 lg:grid-cols-2 lg:items-stretch">
          <MissionGraph />
          <MissionControlLiveEvents />
        </div>

        {/* Mission builder + dynamic agent */}
        <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
          <MissionBuilderPanel />
          <CreateAgentPanel />
        </div>

        {/* Bottom band: artifacts */}
        <ArtifactsPanel />

        {/* Full orchestration dashboard (assignments, permissions, maintenance, …) */}
        <MissionControlPage />
      </main>
    </div>
  );
}
