import {useEffect, useRef} from 'react';

import {connectMobileChatWebSocket} from '../services/websocket';
import {useAuthStore} from '../store/authStore';
import {useChatStore} from '../store/chatStore';

/** Subscribe to mobile WS echo stream when token exists. */
export function useMobileChatSocket(enabled: boolean) {
  const token = useAuthStore(s => s.token);
  const pushMessage = useChatStore(s => s.pushMessage);
  const handleRef = useRef<{close: () => void} | null>(null);

  useEffect(() => {
    if (!enabled || !token) {
      return;
    }
    const h = connectMobileChatWebSocket(token, msg => {
      if (msg.type === 'message') {
        pushMessage({
          id: `${Date.now()}`,
          text: JSON.stringify(msg.echo ?? msg),
          isUser: false,
          createdAt: new Date(),
        });
      }
    });
    handleRef.current = h;
    return () => h?.close();
  }, [enabled, token, pushMessage]);
}
