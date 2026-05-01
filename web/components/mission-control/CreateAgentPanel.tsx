"use client";

import { Bot, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";
import { webFetch } from "@/lib/api";
import { isConfigured } from "@/lib/config";
const TOOL_PRESETS = [
  { id: "web", label: "Web fetch / research" },
  { id: "summarize", label: "Summarize long inputs" },
  { id: "code", label: "Code-oriented reasoning" },
];

/**
 * Builds a natural-language prompt for POST `/custom-agents` (parsed server-side).
 */
export function CreateAgentPanel({ onCreated }: { onCreated?: () => void }) {
  const [handle, setHandle] = useState("");
  const [role, setRole] = useState("");
  const [tools, setTools] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const toggleTool = (id: string) => {
    setTools((t) => ({ ...t, [id]: !t[id] }));
  };

  const buildPrompt = (): string => {
    const h = handle.trim().replace(/^@+/, "");
    const baseHandle = h || "my-agent";
    const skills = TOOL_PRESETS.filter((p) => tools[p.id])
      .map((p) => p.label)
      .join(", ");
    const roleLine = role.trim() || "assist with focused research and clear summaries";
    return (
      `Create a custom agent called @${baseHandle}. It should ${roleLine}.` +
      (skills ? ` Skills: ${skills}.` : "")
    );
  };

  const submit = async () => {
    if (!isConfigured()) {
      setErr("Configure user id and API base on the login page.");
      return;
    }
    const prompt = buildPrompt();
    if (prompt.length < 3) {
      setErr("Describe the agent (handle + role).");
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const out = await webFetch<{ ok?: boolean; message?: string }>("/custom-agents", {
        method: "POST",
        body: JSON.stringify({ prompt }),
      });
      setMsg(out.message || "Created.");
      onCreated?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950/70 px-4 py-4">
      <div className="mb-3 flex items-center gap-2">
        <Bot className="h-4 w-4 text-sky-400" />
        <h2 className="text-sm font-medium text-zinc-200">Create custom agent</h2>
      </div>
      <p className="mb-3 text-xs text-zinc-500">
        Generates a prompt for the parser (`@handle`, role, optional skills). Requires permission to create agents on your account.
      </p>

      <label className="block text-[11px] font-medium uppercase tracking-wide text-zinc-500">Handle</label>
      <input
        value={handle}
        onChange={(e) => setHandle(e.target.value)}
        placeholder="e.g. patent-scout"
        className="mt-1 w-full rounded-md border border-zinc-800 bg-black/40 px-3 py-2 font-mono text-sm text-zinc-100 placeholder:text-zinc-600"
      />

      <label className="mt-3 block text-[11px] font-medium uppercase tracking-wide text-zinc-500">Role</label>
      <textarea
        value={role}
        onChange={(e) => setRole(e.target.value)}
        rows={3}
        placeholder="What this agent should do day-to-day…"
        className="mt-1 w-full resize-y rounded-md border border-zinc-800 bg-black/40 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
      />

      <p className="mt-3 text-[11px] font-medium uppercase tracking-wide text-zinc-500">Tools / emphasis</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {TOOL_PRESETS.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => toggleTool(p.id)}
            className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
              tools[p.id]
                ? "border-sky-500/60 bg-sky-950/50 text-sky-200"
                : "border-zinc-700 bg-zinc-900/60 text-zinc-400 hover:border-zinc-600"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {err ? (
        <p className="mt-2 rounded border border-rose-500/30 bg-rose-950/30 px-2 py-1.5 text-xs text-rose-200">{err}</p>
      ) : null}
      {msg ? (
        <p className="mt-2 flex items-start gap-2 rounded border border-emerald-500/25 bg-emerald-950/25 px-2 py-1.5 text-xs text-emerald-200">
          <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {msg}
        </p>
      ) : null}

      <button
        type="button"
        onClick={() => void submit()}
        disabled={busy}
        className="mt-3 inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50"
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        Create agent
      </button>

      <details className="mt-3 text-xs text-zinc-600">
        <summary className="cursor-pointer text-zinc-500">Preview prompt</summary>
        <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap rounded border border-zinc-800 bg-black/40 p-2 font-mono text-[11px] text-zinc-400">
          {buildPrompt()}
        </pre>
      </details>
    </section>
  );
}
