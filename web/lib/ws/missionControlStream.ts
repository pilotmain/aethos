/**
 * Phase 14 — single shared Mission Control WebSocket (one connection per tab).
 * All Mission Control surfaces subscribe here instead of opening duplicate sockets.
 */

import { missionControlEventsWsUrl } from "@/lib/mission-control/eventsWsUrl";

export type MissionStreamConnState = "connecting" | "open" | "reconnecting" | "error";

const msgListeners = new Set<(data: unknown) => void>();
const connListeners = new Set<(s: MissionStreamConnState) => void>();

let ws: WebSocket | null = null;
let stopped = false;
let attempt = 0;
let reconnectTimer: number | undefined;
let pingTimer: number | undefined;

function notifyConn(s: MissionStreamConnState) {
  connListeners.forEach((l) => l(s));
}

function notifyMsg(data: unknown) {
  msgListeners.forEach((l) => l(data));
}

function scheduleReconnect() {
  if (stopped) return;
  notifyConn("reconnecting");
  const backoff = Math.min(30_000, 500 * Math.pow(2, attempt++));
  reconnectTimer = window.setTimeout(() => connectSocket(), backoff);
}

function connectSocket() {
  if (stopped || typeof window === "undefined") return;
  if (pingTimer !== undefined) {
    window.clearInterval(pingTimer);
    pingTimer = undefined;
  }
  notifyConn("connecting");
  const url = missionControlEventsWsUrl();
  ws = new WebSocket(url);
  ws.onopen = () => {
    attempt = 0;
    notifyConn("open");
  };
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(String(e.data)) as unknown;
      notifyMsg(data);
    } catch {
      /* ignore non-JSON */
    }
  };
  ws.onerror = () => notifyConn("error");
  ws.onclose = () => {
    ws = null;
    if (pingTimer !== undefined) {
      window.clearInterval(pingTimer);
      pingTimer = undefined;
    }
    if (!stopped) scheduleReconnect();
  };

  pingTimer = window.setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) ws.send("ping");
  }, 25_000);
}

/** Idempotent: ensures exactly one reconnecting socket for this module. */
export function ensureMissionControlStream(): void {
  if (typeof window === "undefined") return;
  stopped = false;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  connectSocket();
}

export function subscribeMissionMessages(handler: (data: unknown) => void): () => void {
  msgListeners.add(handler);
  ensureMissionControlStream();
  return () => {
    msgListeners.delete(handler);
  };
}

export function subscribeMissionConnection(handler: (s: MissionStreamConnState) => void): () => void {
  connListeners.add(handler);
  ensureMissionControlStream();
  return () => connListeners.delete(handler);
}

export function disconnectMissionControlStream(): void {
  stopped = true;
  window.clearTimeout(reconnectTimer);
  reconnectTimer = undefined;
  if (pingTimer !== undefined) {
    window.clearInterval(pingTimer);
    pingTimer = undefined;
  }
  ws?.close();
  ws = null;
}

/** Close and reconnect (e.g. Retry in UI). */
export function forceReconnectMissionStream(): void {
  disconnectMissionControlStream();
  stopped = false;
  connectSocket();
}
