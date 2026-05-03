"use client";

export type SafetyReadiness = {
  sandbox_mode?: string;
  sandbox_docker_available?: boolean;
  credential_vault_provider?: string;
  network_egress_mode?: string;
  network_egress_recent_blocked?: number;
  token_budget_per_request?: number;
  block_over_token_budget?: boolean;
  strict_privacy_mode?: boolean;
  local_first?: boolean;
  voice_enabled?: boolean;
  voice_transcribe_provider?: string;
  skill_package_count?: number;
  install_hint?: string;
};

function badge(shellLight: boolean, ok: boolean, label: string) {
  const base = shellLight
    ? ok
      ? "border-emerald-300 bg-emerald-50 text-emerald-950"
      : "border-amber-300 bg-amber-50 text-amber-950"
    : ok
      ? "border-emerald-500/40 bg-emerald-950/35 text-emerald-100"
      : "border-amber-500/40 bg-amber-950/35 text-amber-100";
  return (
    <span className={`rounded-md border px-2 py-0.5 text-[10px] font-medium ${base}`}>{label}</span>
  );
}

export function SafetyAndReadinessPanel({
  data,
  loading,
  shellLight,
}: {
  data: SafetyReadiness | Record<string, unknown> | undefined;
  loading: boolean;
  shellLight: boolean;
}) {
  if (loading && !data) {
    return (
      <section
        className={`rounded-xl border p-4 text-sm ${
          shellLight ? "border-zinc-200 bg-white text-zinc-700" : "border-zinc-800 bg-zinc-950 text-zinc-200"
        }`}
      >
        Loading safety & readiness…
      </section>
    );
  }
  if (!data) return null;

  const egressOk = (data.network_egress_recent_blocked ?? 0) === 0;
  const dockerOk = data.sandbox_docker_available !== false;

  return (
    <section
      className={`rounded-xl border p-4 ${
        shellLight ? "border-zinc-200 bg-white text-zinc-800" : "border-zinc-800 bg-zinc-950 text-zinc-100"
      }`}
    >
      <h2 className={`text-sm font-semibold ${shellLight ? "text-zinc-900" : "text-zinc-50"}`}>
        Safety & readiness
      </h2>
      <p className={`mt-1 text-xs ${shellLight ? "text-zinc-500" : "text-zinc-500"}`}>
        Sandbox mode, vault, egress policy, token budget, and local skill packages.
      </p>
      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <div className="flex flex-wrap items-center gap-2">
          <dt className={shellLight ? "text-zinc-500" : "text-zinc-500"}>Sandbox</dt>
          <dd className="font-mono text-[11px]">{d.sandbox_mode ?? "—"}</dd>
          {badge(shellLight, dockerOk, dockerOk ? "docker CLI" : "no docker")}
        </div>
        <div>
          <dt className={shellLight ? "text-zinc-500" : "text-zinc-500"}>Credential vault</dt>
          <dd className="font-mono text-[11px]">{d.credential_vault_provider ?? "—"}</dd>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <dt className={shellLight ? "text-zinc-500" : "text-zinc-500"}>Egress</dt>
          <dd className="font-mono text-[11px]">{d.network_egress_mode ?? "—"}</dd>
          {badge(shellLight, egressOk, egressOk ? "no recent blocks" : "recent blocks")}
        </div>
        <div>
          <dt className={shellLight ? "text-zinc-500" : "text-zinc-500"}>Token budget / request</dt>
          <dd className="font-mono text-[11px]">
            {d.token_budget_per_request ?? "—"}
            {d.block_over_token_budget ? " · hard cap" : ""}
          </dd>
        </div>
        <div>
          <dt className={shellLight ? "text-zinc-500" : "text-zinc-500"}>Privacy</dt>
          <dd className="font-mono text-[11px]">
            {d.strict_privacy_mode ? "strict" : "standard"}{" "}
            {d.local_first ? "· local-first" : ""}
          </dd>
        </div>
        <div>
          <dt className={shellLight ? "text-zinc-500" : "text-zinc-500"}>Voice</dt>
          <dd className="font-mono text-[11px]">
            {d.voice_enabled ? "on" : "off"} ({d.voice_transcribe_provider ?? "local"})
          </dd>
        </div>
        <div>
          <dt className={shellLight ? "text-zinc-500" : "text-zinc-500"}>Packaged skills</dt>
          <dd className="font-mono text-[11px]">{d.skill_package_count ?? 0}</dd>
        </div>
      </dl>
      {d.install_hint ? (
        <p className={`mt-3 text-[11px] ${shellLight ? "text-zinc-500" : "text-zinc-500"}`}>{d.install_hint}</p>
      ) : null}
    </section>
  );
}
