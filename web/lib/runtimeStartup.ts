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
  runtime_startup_lock?: {
    holder_pid?: number | null;
    phase?: string | null;
    serialized_hydration?: boolean;
  };
  runtime_process_supervision?: {
    conflicts?: string[];
    observer_mode?: boolean;
  };
};

export function startupBanner(payload: RuntimeStartupPayload | undefined): string | null {
  const exp = payload?.runtime_startup_experience;
  const lock = payload?.runtime_startup_lock;
  const sup = payload?.runtime_process_supervision;
  if (!exp?.partial_mode && !lock?.holder_pid && !(sup?.conflicts?.length)) return null;
  const label = exp?.current_stage?.label ?? (lock?.phase ? `Loading ${lock.phase}` : "Starting runtime");
  const pct = exp?.readiness_percent != null ? Math.round(exp.readiness_percent * 100) : null;
  let base = pct != null ? `${label} — ${pct}% ready` : label;
  if (lock?.serialized_hydration && lock?.holder_pid) {
    base = `${base} (hydration serialized)`;
  }
  if (sup?.conflicts?.length) {
    base = `${base}. Process supervision: ${sup.conflicts[0]}`;
  }
  if (exp?.partial_availability_notice) {
    return `${base}. ${exp.partial_availability_notice}`;
  }
  return base;
}
