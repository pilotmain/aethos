"use client";

import { Loader2, Play, Rocket } from "lucide-react";
import { useState } from "react";
import { webFetch } from "@/lib/api";
import { isConfigured, readConfig } from "@/lib/config";

/**
 * Compose gateway mission text and POST to `/mission-control/gateway/run`.
 */
export function MissionBuilderPanel() {
  const [title, setTitle] = useState("");
  const [tasks, setTasks] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const run = async () => {
    if (!isConfigured()) {
      setErr("Configure user id and API base on the login page.");
      return;
    }
    const t = title.trim();
    const body = tasks.trim();
    if (!body) {
      setErr("Add at least one task line.");
      return;
    }
    const uid = readConfig().userId;
    const missionTitle = t || "Untitled mission";
    const text = `Mission: ${missionTitle}\n\n${body}`;
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const out = await webFetch<Record<string, unknown>>("/mission-control/gateway/run", {
        method: "POST",
        body: JSON.stringify({ text, user_id: uid }),
      });
      setResult(JSON.stringify(out, null, 2));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950/70 px-4 py-4">
      <div className="mb-3 flex items-center gap-2">
        <Rocket className="h-4 w-4 text-violet-400" />
        <h2 className="text-sm font-medium text-zinc-200">Mission builder</h2>
      </div>
      <p className="mb-3 text-xs text-zinc-500">
        Sends structured text through the Nexa gateway (same path as channels). Use loose lines like{" "}
        <span className="font-mono text-zinc-400">Researcher: …</span> / <span className="font-mono text-zinc-400">Analyst: …</span>.
      </p>

      <label className="block text-[11px] font-medium uppercase tracking-wide text-zinc-500">Mission name</label>
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="e.g. Quarterly competitive scan"
        className="mt-1 w-full rounded-md border border-zinc-800 bg-black/40 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
      />

      <label className="mt-3 block text-[11px] font-medium uppercase tracking-wide text-zinc-500">Tasks</label>
      <textarea
        value={tasks}
        onChange={(e) => setTasks(e.target.value)}
        rows={6}
        placeholder={`Researcher: summarize three trends in warehouse robotics.\nAnalyst: draft a short memo citing the researcher.`}
        className="mt-1 w-full resize-y rounded-md border border-zinc-800 bg-black/40 px-3 py-2 font-mono text-[13px] text-zinc-100 placeholder:text-zinc-600"
      />

      {err ? (
        <p className="mt-2 rounded border border-rose-500/30 bg-rose-950/30 px-2 py-1.5 text-xs text-rose-200">{err}</p>
      ) : null}

      <button
        type="button"
        onClick={() => void run()}
        disabled={busy}
        className="mt-3 inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        Run mission
      </button>

      {result ? (
        <pre className="mt-3 max-h-48 overflow-auto rounded-md border border-zinc-800 bg-black/50 p-3 font-mono text-[11px] text-zinc-300">
          {result}
        </pre>
      ) : null}
    </section>
  );
}
