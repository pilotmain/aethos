export type MissionWsConnectionState = "connecting" | "open" | "reconnecting" | "error";

/**
 * @deprecated Phase 14 — use `@/lib/ws/missionControlStream` for a single shared Mission Control socket.
 *
 * WebSocket with exponential backoff reconnect (Phase 11).
 * Caller supplies `onMessage`; optional `pingMs` keeps connections alive.
 */
export function connectReconnectingMissionWs(
  url: string,
  opts: {
    onMessage: (data: string) => void;
    onState?: (s: MissionWsConnectionState) => void;
    pingMs?: number;
  },
): () => void {
  let attempt = 0;
  let ws: WebSocket | null = null;
  /** Browser timer id (distinct from NodeJS.Timeout during Next typecheck). */
  let reconnectTimer: number | undefined;
  let stopped = false;

  const pingMs = opts.pingMs ?? 25_000;

  function scheduleReconnect() {
    if (stopped) return;
    opts.onState?.("reconnecting");
    const backoff = Math.min(30_000, 500 * Math.pow(2, attempt++));
    reconnectTimer = window.setTimeout(connect, backoff);
  }

  function connect() {
    if (stopped) return;
    opts.onState?.("connecting");
    ws = new WebSocket(url);
    ws.onopen = () => {
      attempt = 0;
      opts.onState?.("open");
    };
    ws.onmessage = (e) => opts.onMessage(String(e.data));
    ws.onerror = () => opts.onState?.("error");
    ws.onclose = () => {
      ws = null;
      if (!stopped) scheduleReconnect();
    };
  }

  connect();

  const ping = window.setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) ws.send("ping");
  }, pingMs);

  return () => {
    stopped = true;
    window.clearInterval(ping);
    if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
    ws?.close();
  };
}
