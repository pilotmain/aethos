/**
 * Phase 14 — shared Mission Control HTTP snapshot cache (graph + state).
 * Live WS events are appended separately (see appendMissionLiveEvent).
 */

import { webFetch } from "@/lib/api";
import { DEFAULT_API_BASE, isConfigured, readConfig } from "@/lib/config";

export const MC_MAX_UI_EVENTS = 500;

export type MissionGraphPayload = {
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
};

let graph: MissionGraphPayload | null = null;
let mcState: Record<string, unknown> | null = null;
let liveEvents: unknown[] = [];

const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((l) => l());
}

export function subscribeMissionStore(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function graphHttpUrl(): string {
  const c = readConfig();
  const base = (c.apiBase?.trim() || DEFAULT_API_BASE).replace(/\/$/, "");
  const uid = (c.userId || "").trim();
  const q = uid ? `?user_id=${encodeURIComponent(uid)}` : "";
  return `${base}/api/v1/mission-control/graph${q}`;
}

/** Parallel fetch graph + authenticated state (single coordinated refresh). */
export async function refreshMissionControlStore(): Promise<void> {
  if (!isConfigured()) {
    graph = null;
    mcState = null;
    notify();
    return;
  }
  const uid = readConfig().userId;
  try {
    const [gr, st] = await Promise.all([
      fetch(graphHttpUrl()).then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status))))),
      webFetch<Record<string, unknown>>(
        `/mission-control/state?user_id=${encodeURIComponent(uid)}`,
      ),
    ]);
    graph = {
      nodes: Array.isArray((gr as MissionGraphPayload).nodes) ? (gr as MissionGraphPayload).nodes : [],
      edges: Array.isArray((gr as MissionGraphPayload).edges) ? (gr as MissionGraphPayload).edges : [],
    };
    mcState = st;
  } catch {
    /* keep previous snapshot on transient failure */
  } finally {
    notify();
  }
}

export function appendMissionLiveEvent(ev: unknown): void {
  liveEvents = [...liveEvents, ev].slice(-MC_MAX_UI_EVENTS);
  notify();
}

export function getMissionGraph(): MissionGraphPayload | null {
  return graph;
}

export function getMissionState(): Record<string, unknown> | null {
  return mcState;
}

export function getMissionLiveEvents(): unknown[] {
  return liveEvents;
}

export function clearMissionLiveEvents(): void {
  liveEvents = [];
  notify();
}
