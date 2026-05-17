"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";

type TourTopic = { id?: string; title?: string; path?: string };
type OnboardingQuestion = { id?: string; label?: string; optional?: boolean };

type Payload = {
  mission_control_first_run?: {
    welcome?: string;
    steps?: { id?: string; title?: string; path?: string }[];
    first_run_complete?: boolean;
    first_run_onboarding_pending?: boolean;
    first_run_onboarding?: {
      pending?: boolean;
      welcome?: string;
      questions?: OnboardingQuestion[];
    };
    guided_tour?: {
      active?: boolean;
      completed?: boolean;
      dismissed?: boolean;
      topics?: TourTopic[];
    };
  };
  operational_readiness_summary?: { readiness_score?: number; production_ready?: boolean };
};

export default function OnboardingPage() {
  const [data, setData] = useState<Payload>({});
  const [error, setError] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [tone, setTone] = useState("calm");
  const [goals, setGoals] = useState("");

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
  const tour = fr?.guided_tour;
  const pendingOnboarding = fr?.first_run_onboarding_pending;

  const dismissTour = async () => {
    try {
      await apiFetch("/mission-control/onboarding/tour-dismiss", { method: "POST" });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not dismiss tour");
    }
  };

  const completeTour = async () => {
    try {
      await apiFetch("/mission-control/onboarding/tour-complete", { method: "POST" });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not complete tour");
    }
  };

  const saveProfile = async () => {
    try {
      await apiFetch("/mission-control/onboarding/complete-profile", {
        method: "POST",
        body: JSON.stringify({
          profile: {
            display_name: displayName || undefined,
            tone: tone || undefined,
            goals: goals || undefined,
          },
        }),
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save profile");
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Welcome to AethOS</h1>
        <p className="mt-1 text-sm text-muted-foreground">First-run guidance — calm, premium, orchestrator-led</p>
      </header>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {fr?.welcome ? <p className="rounded-lg border border-border/40 bg-card/30 px-4 py-3 text-sm whitespace-pre-line">{fr.welcome}</p> : null}
      {pendingOnboarding ? (
        <section className="rounded-lg border border-border/50 bg-card/40 p-4 space-y-3">
          <h2 className="text-sm font-medium">First-run onboarding</h2>
          <p className="text-sm text-muted-foreground">Optional — helps AethOS adapt to how you work.</p>
          <label className="block text-sm">
            What should I call you?
            <input
              className="mt-1 w-full rounded border border-border/60 bg-background px-3 py-2 text-sm"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Preferred tone
            <input
              className="mt-1 w-full rounded border border-border/60 bg-background px-3 py-2 text-sm"
              value={tone}
              onChange={(e) => setTone(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Main goals
            <input
              className="mt-1 w-full rounded border border-border/60 bg-background px-3 py-2 text-sm"
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
            />
          </label>
          <button type="button" className="text-sm text-primary hover:underline" onClick={() => void saveProfile()}>
            Save and continue
          </button>
        </section>
      ) : null}
      {tour?.active ? (
        <section className="rounded-lg border border-border/50 bg-card/40 p-4 space-y-3">
          <h2 className="text-sm font-medium">Guided tour</h2>
          <p className="text-sm text-muted-foreground">
            AethOS will introduce Office, runtime, workers, governance, and recovery — dismiss anytime.
          </p>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {(tour.topics ?? []).map((t) => (
              <li key={t.id}>
                <Link href={t.path ?? "#"} className="text-primary hover:underline">
                  {t.title}
                </Link>
              </li>
            ))}
          </ul>
          <div className="flex gap-3 text-sm">
            <button type="button" className="text-primary hover:underline" onClick={() => void completeTour()}>
              Mark tour complete
            </button>
            <button type="button" className="text-muted-foreground hover:underline" onClick={() => void dismissTour()}>
              Dismiss
            </button>
          </div>
        </section>
      ) : null}
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
