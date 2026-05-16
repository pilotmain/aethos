"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type Payload = {
  operational_governance_story?: string;
  trust_narratives?: string[];
  accountability_highlights?: string[];
  escalation_explanations?: { title?: string; explanation?: string }[];
  governance_experience_layer?: { headline?: string };
};

export default function GovernanceExperiencePage() {
  const [data, setData] = useState<Payload>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const g = await apiFetch<Payload>("/mission-control/governance-experience");
      setData(g);
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
        <h1 className="text-xl font-semibold">Governance experience</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Operational history, trust narratives, and accountability — calm enterprise storytelling
        </p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {data.operational_governance_story ? (
        <p className="rounded-lg border border-border/40 bg-card/30 px-4 py-3 text-sm">{data.operational_governance_story}</p>
      ) : null}
      {data.trust_narratives?.length ? (
        <section className="space-y-2 text-sm">
          <p className="text-xs uppercase text-muted-foreground">Trust</p>
          {data.trust_narratives.map((t, i) => (
            <p key={i} className="text-muted-foreground">
              {t}
            </p>
          ))}
        </section>
      ) : null}
      {data.escalation_explanations?.length ? (
        <section className="space-y-2 text-sm">
          <p className="text-xs uppercase text-muted-foreground">Escalations</p>
          {data.escalation_explanations.map((e, i) => (
            <p key={i} className="border-b border-border/30 pb-2">
              <span className="font-medium">{e.title}</span> — {e.explanation}
            </p>
          ))}
        </section>
      ) : null}
      <nav className="flex gap-3 text-sm">
        <Link href="/mission-control/governance" className="text-primary hover:underline">
          Timeline
        </Link>
        <Link href="/mission-control/timeline-experience" className="text-primary hover:underline">
          Timeline experience
        </Link>
      </nav>
    </div>
  );
}
