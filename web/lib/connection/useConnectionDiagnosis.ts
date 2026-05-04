"use client";

import { useEffect, useState } from "react";
import { DEFAULT_API_BASE, readConfig } from "@/lib/config";
import { diagnoseConnection } from "./diagnoseConnection";
import type { ConnectionDiagnosis } from "./types";

/**
 * When `trigger` is non-empty, probes `/api/v1/health` for the saved API base (and alternates).
 */
export function useConnectionDiagnosis(trigger: string | null | undefined): ConnectionDiagnosis | null {
  const [d, setD] = useState<ConnectionDiagnosis | null>(null);
  useEffect(() => {
    if (!trigger) {
      setD(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      const c = readConfig();
      const res = await diagnoseConnection(c.apiBase || DEFAULT_API_BASE);
      if (!cancelled) {
        setD(res);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [trigger]);
  return d;
}
