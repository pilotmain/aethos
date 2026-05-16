"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type Payload = {
  mission_control_first_run?: {
    welcome?: string;
    steps?: { id?: string; title?: string; path?: string }[];
    first_run_complete?: boolean;
  };
  operational_readiness_summary?: { readiness_score?: number; production_ready?: boolean };
};

export default function OnboardingPage() {
  const [data, setData] = useState<Payload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await apiFetch<Payload>("/mission-control/onboarding"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const fr = data.mission_control_first_run;

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Welcome to AethOS</h1>
        <p className="mt-1 text-sm text-muted-foreground">First-run guidance — calm, premium, orchestrator-led</p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {fr?.welcome ? <p className="rounded-lg border border-border/40 bg-card/30 px-4 py-3 text-sm">{fr.welcome}</p> : null}
      <ol className="list-decimal space-y-2 pl-5 text-sm">
        {(fr?.steps ?? []).map((s) => (
          <li key={s.id}>
            <Link href={s.path ?? "#"} className="text-primary hover:underline">
              {s.title}
            </Link>
          </li>
        ))}
      </ol>
      <Link href="/mission-control/office" className="text-sm text-primary hover:underline">
        Go to Office
      </Link>
    </div>
  );
}
