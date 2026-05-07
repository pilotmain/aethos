"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { DEFAULT_API_BASE, readConfig } from "@/lib/config";

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
  const [userId, setUserId] = useState<string | null>(null);
  const [bearerToken, setBearerToken] = useState<string | null>(null);
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const stored = readConfig();
    const nextUserId = stored.userId.trim() || null;
    const nextToken = stored.token.trim() || null;
    const nextApiBase = (stored.apiBase || DEFAULT_API_BASE).trim().replace(/\/$/, "");

    setUserId(nextUserId);
    setBearerToken(nextToken);
    setApiBase(nextApiBase);

    if (!nextUserId) {
      setIsConnected(false);
      return undefined;
    }

    const controller = new AbortController();
    fetch(`${nextApiBase}/api/v1/user/settings`, {
      headers: buildAuthHeaders(nextUserId, nextToken),
      cache: "no-store",
      signal: controller.signal,
    })
      .then((response) => setIsConnected(response.ok))
      .catch(() => setIsConnected(false));

    return () => controller.abort();
  }, []);

  const value = useMemo(
    () => ({ userId, bearerToken, apiBase, isConnected }),
    [apiBase, bearerToken, isConnected, userId],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
