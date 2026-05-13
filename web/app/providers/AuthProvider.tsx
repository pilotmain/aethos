"use client";

import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { DEFAULT_API_BASE, readConfig, saveConfig } from "@/lib/config";

type AuthContextType = {
  userId: string | null;
  bearerToken: string | null;
  apiBase: string | null;
  isConnected: boolean;
};

const AuthContext = createContext<AuthContextType>({
  userId: null,
  bearerToken: null,
  apiBase: null,
  isConnected: false,
});

function buildAuthHeaders(userId: string | null, bearerToken: string | null): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (userId) {
    headers["X-User-Id"] = userId;
  }
  if (bearerToken) {
    headers.Authorization = `Bearer ${bearerToken}`;
  }
  return headers;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [userId, setUserId] = useState<string | null>(null);
  const [bearerToken, setBearerToken] = useState<string | null>(null);
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    const run = async () => {
      try {
        const r = await fetch("/api/setup-creds", { cache: "no-store", signal: controller.signal });
        const creds = (await r.json()) as { api_base?: string; user_id?: string; bearer_token?: string };
        if (cancelled) {
          return;
        }
        if (creds.user_id && creds.api_base) {
          const cur = readConfig();
          const uid = creds.user_id.trim();
          const apply = !cur.userId.trim() || cur.userId.trim() === uid;
          if (apply) {
            saveConfig({
              apiBase: creds.api_base.trim().replace(/\/$/, "") || cur.apiBase || DEFAULT_API_BASE,
              userId: uid,
              token: (creds.bearer_token ?? cur.token ?? "").trim(),
            });
          }
        }
      } catch {
        /* ignore */
      }
      if (cancelled) {
        return;
      }
      const stored = readConfig();
      const nextUserId = stored.userId.trim() || null;
      const nextToken = stored.token.trim() || null;
      const nextApiBase = (stored.apiBase || DEFAULT_API_BASE).trim().replace(/\/$/, "");

      setUserId(nextUserId);
      setBearerToken(nextToken);
      setApiBase(nextApiBase);

      if (!nextUserId) {
        setIsConnected(false);
        return;
      }

      try {
        const response = await fetch(`${nextApiBase}/api/v1/user/settings`, {
          headers: buildAuthHeaders(nextUserId, nextToken),
          cache: "no-store",
          signal: controller.signal,
        });
        if (!cancelled) {
          setIsConnected(response.ok);
        }
      } catch {
        if (!cancelled) {
          setIsConnected(false);
        }
      }
    };

    void run();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [pathname]);

  const value = useMemo(
    () => ({ userId, bearerToken, apiBase, isConnected }),
    [apiBase, bearerToken, isConnected, userId],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
