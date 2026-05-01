"use client";

import { FolderGit2, ListOrdered, Terminal } from "lucide-react";
import type { ReactNode } from "react";

export type DevWorkspaceRow = {
  id: string;
  name?: string;
  repo_path?: string;
  status?: string;
  created_at?: string | null;
};

export type DevRunRow = {
  id: string;
  workspace_id?: string;
  goal?: string;
  status?: string;
  created_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
};

function panelTitle(shellLight: boolean) {
  return shellLight ? "text-zinc-900" : "text-zinc-100";
}

function subtle(shellLight: boolean) {
  return shellLight ? "text-zinc-600" : "text-zinc-400";
}

/** Phase 23 — dev workspaces + runs from Mission Control snapshot. */
export function DevOpsPanel(props: {
  shellLight: boolean;
  workspaces: DevWorkspaceRow[] | undefined;
  runs: DevRunRow[] | undefined;
  loading?: boolean;
}) {
  const { shellLight, workspaces, runs, loading } = props;
  const ws = workspaces ?? [];
  const rs = runs ?? [];

  const wrap = (body: ReactNode) => (
    <section
      className={`rounded-xl border p-4 transition-colors duration-300 ${
        shellLight ? "border-zinc-200 bg-white/90" : "border-zinc-800/80 bg-zinc-950/50"
      }`}
    >
      {body}
    </section>
  );

  return wrap(
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Terminal className={`h-4 w-4 ${subtle(shellLight)}`} aria-hidden />
        <h2 className={`text-sm font-semibold ${panelTitle(shellLight)}`}>Dev workspace (Phase 23)</h2>
        {loading ? (
          <span className={`text-xs ${subtle(shellLight)}`}>Loading…</span>
        ) : null}
      </div>
      <p className={`mb-4 text-xs ${subtle(shellLight)}`}>
        Register repos via <code className="font-mono text-[11px]">POST /api/v1/dev/workspaces</code> and run missions via{" "}
        <code className="font-mono text-[11px]">POST /api/v1/dev/runs</code>. Allowlisted commands only; secrets are redacted in stored output.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <div className={`mb-2 flex items-center gap-2 text-xs font-medium ${subtle(shellLight)}`}>
            <FolderGit2 className="h-3.5 w-3.5" aria-hidden />
            Workspaces ({ws.length})
          </div>
          {ws.length === 0 ? (
            <p className={`text-xs ${subtle(shellLight)}`}>None yet.</p>
          ) : (
            <ul className="max-h-40 space-y-2 overflow-y-auto text-xs">
              {ws.map((w) => (
                <li
                  key={w.id}
                  className={`rounded border px-2 py-1.5 font-mono ${
                    shellLight ? "border-zinc-200 bg-zinc-50" : "border-zinc-700 bg-zinc-900/40"
                  }`}
                >
                  <span className={shellLight ? "text-zinc-800" : "text-zinc-200"}>{w.name || w.id}</span>
                  <span className={`block truncate ${subtle(shellLight)}`}>{w.repo_path}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <div className={`mb-2 flex items-center gap-2 text-xs font-medium ${subtle(shellLight)}`}>
            <ListOrdered className="h-3.5 w-3.5" aria-hidden />
            Recent dev runs ({rs.length})
          </div>
          {rs.length === 0 ? (
            <p className={`text-xs ${subtle(shellLight)}`}>None yet.</p>
          ) : (
            <ul className="max-h-40 space-y-2 overflow-y-auto text-xs">
              {rs.slice(0, 12).map((r) => (
                <li
                  key={r.id}
                  className={`rounded border px-2 py-1.5 ${
                    shellLight ? "border-zinc-200 bg-zinc-50" : "border-zinc-700 bg-zinc-900/40"
                  }`}
                >
                  <span className={shellLight ? "text-emerald-800" : "text-emerald-400"}>{r.status}</span>
                  <span className={`block ${shellLight ? "text-zinc-800" : "text-zinc-200"}`}>{r.goal}</span>
                  {r.error ? (
                    <span className={`block truncate ${shellLight ? "text-rose-700" : "text-rose-300"}`}>{r.error}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}
