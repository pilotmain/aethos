export type HydrationStage = {
  id: string;
  label: string;
  complete?: boolean;
};

export type RuntimeStartupPayload = {
  runtime_startup_experience?: {
    current_stage?: { id?: string; label?: string };
    readiness_percent?: number;
    partial_mode?: boolean;
    partial_availability_notice?: string | null;
    stages?: HydrationStage[];
  };
};

export function startupBanner(payload: RuntimeStartupPayload | undefined): string | null {
  const exp = payload?.runtime_startup_experience;
  if (!exp?.partial_mode) return null;
  const label = exp.current_stage?.label ?? "Starting runtime";
  const pct = exp.readiness_percent != null ? Math.round(exp.readiness_percent * 100) : null;
  const base = pct != null ? `${label} — ${pct}% ready` : label;
  return exp.partial_availability_notice ? `${base}. ${exp.partial_availability_notice}` : base;
}
