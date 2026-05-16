"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type Payload = {
  explainability_center?: { headline?: string };
  runtime_decision_explanations?: { topic?: string; reason?: string }[];
  recommendation_explanations?: { message?: string; why?: string }[];
  recovery_explanation?: string;
};

export default function ExplainabilityPage() {
  const [data, setData] = useState<Payload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await apiFetch<Payload>("/mission-control/explainability"));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Explainability</h1>
        <p className="mt-1 text-sm text-muted-foreground">Why the runtime chose this posture — advisory and bounded</p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {data.recovery_explanation ? <p className="text-sm">{data.recovery_explanation}</p> : null}
      <ul className="space-y-2 text-sm text-muted-foreground">
        {(data.runtime_decision_explanations ?? []).map((e, i) => (
          <li key={i}>
            <span className="font-medium text-foreground">{e.topic}</span> — {e.reason}
          </li>
        ))}
      </ul>
      <Link href="/mission-control/runtime-overview" className="text-sm text-primary hover:underline">
        Runtime overview
      </Link>
    </div>
  );
}
