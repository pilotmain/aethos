export type HydrationStage = {
  id: string;
  label: string;
  complete?: boolean;
};

export type WarmupCheckItem = {
  id?: string;
  label?: string;
  complete?: boolean;
  warming?: boolean;
};

export type RuntimeStartupPayload = {
  runtime_startup_experience?: {
    current_stage?: { id?: string; label?: string };
    readiness_percent?: number;
    operator_readiness_state?: string;
    office_home_intro?: string;
    partial_mode?: boolean;
    partial_availability_notice?: string | null;
    stages?: HydrationStage[];
  };
  runtime_warmup_awareness?: {
    headline?: string;
    readiness_percent?: number;
    checklist?: WarmupCheckItem[];
    partial_mode?: boolean;
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

export function warmupChecklist(payload: RuntimeStartupPayload | undefined): WarmupCheckItem[] {
  return payload?.runtime_warmup_awareness?.checklist ?? [];
}

export function startupBanner(payload: RuntimeStartupPayload | undefined): string | null {
  const exp = payload?.runtime_startup_experience;
  const warmup = payload?.runtime_warmup_awareness;
  const lock = payload?.runtime_startup_lock;
  const sup = payload?.runtime_process_supervision;
  const partial = exp?.partial_mode || warmup?.partial_mode;
  if (!partial && !lock?.holder_pid && !(sup?.conflicts?.length)) return null;
  const headline = warmup?.headline ?? "AethOS is preparing operational services…";
  const label = exp?.current_stage?.label ?? (lock?.phase ? `Loading ${lock.phase}` : "Starting runtime");
  const pctRaw = warmup?.readiness_percent ?? exp?.readiness_percent;
  const pct = pctRaw != null ? Math.round(pctRaw * 100) : null;
  let base = pct != null ? `${headline} ${label} — ${pct}% ready` : `${headline} ${label}`;
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

export function readinessStateLabel(payload: RuntimeStartupPayload | undefined): string | null {
  return payload?.runtime_startup_experience?.operator_readiness_state ?? null;
}
