import { DEFAULT_API_BASE, readConfig } from "@/lib/config";

/** Convert HTTP API base to WebSocket origin (same host, ws/wss). */
export function toWsOrigin(httpBase: string): string {
  try {
    const u = new URL(httpBase.startsWith("http") ? httpBase : `http://${httpBase}`);
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    return u.origin;
  } catch {
    return "ws://127.0.0.1:8010";
  }
}

/** Nexa Next live event bus (mission / task / artifact). */
export function missionControlEventsWsUrl(): string {
  const c = readConfig();
  const base = c.apiBase?.trim() || DEFAULT_API_BASE;
  return `${toWsOrigin(base)}/api/v1/mission-control/events/ws`;
}
