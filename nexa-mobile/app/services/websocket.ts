import {API_BASE_URL, API_PREFIX} from '../utils/constants';

export type WsHandler = (msg: Record<string, unknown>) => void;

export function connectMobileChatWebSocket(
  token: string | null,
  onMessage: WsHandler,
): {close: () => void; ws: WebSocket} | null {
  if (!token) {
    return null;
  }
  const url = `${API_BASE_URL.replace(/^http/, 'ws')}${API_PREFIX}/mobile/ws/chat?token=${encodeURIComponent(
    token,
  )}`;
  const ws = new WebSocket(url);
  ws.onmessage = event => {
    try {
      const parsed = JSON.parse(event.data as string) as Record<string, unknown>;
      onMessage(parsed);
    } catch {
      onMessage({type: 'raw', data: event.data});
    }
  };
  return {
    ws,
    close: () => ws.close(),
  };
}
