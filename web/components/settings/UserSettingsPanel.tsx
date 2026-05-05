"use client";

import { Loader2, Save, Settings2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { webFetch } from "@/lib/api";
import { isConfigured } from "@/lib/config";

export type PrivacyMode = "standard" | "strict" | "paranoid";
export type UiTheme = "dark" | "light";

export type UserSettingsPayload = {
  privacy_mode: PrivacyMode;
  ui_preferences: {
    theme?: UiTheme;
    auto_refresh?: boolean;
  };
};

type ApiSettings = {
  privacy_mode: string;
  ui_preferences: {
    theme?: string;
    auto_refresh?: boolean;
  };
  identity?: { session_id?: string | null; device_id?: string | null };
};

function normPrivacy(m: string): PrivacyMode {
  const x = (m || "standard").toLowerCase();
  if (x === "strict" || x === "paranoid") return x;
  return "standard";
}

function normTheme(t: string | undefined): UiTheme {
  return t === "light" ? "light" : "dark";
}

/** Phase 21 — AethOS user settings with debounced save (500ms) and sync feedback. */
export function UserSettingsPanel({
  onPreferencesApplied,
  compact,
}: {
  onPreferencesApplied?: (prefs: { theme: UiTheme; auto_refresh: boolean }) => void;
  compact?: boolean;
}) {
  const [privacyMode, setPrivacyMode] = useState<PrivacyMode>("standard");
  const [theme, setTheme] = useState<UiTheme>("dark");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [bootstrapped, setBootstrapped] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const debounceRef = useRef<number | undefined>(undefined);

  const load = useCallback(async () => {
    if (!isConfigured()) return;
    setErrorMsg(null);
    try {
      const data = await webFetch<ApiSettings>("/user/settings");
      setPrivacyMode(normPrivacy(data.privacy_mode));
      const ui = data.ui_preferences || {};
      setTheme(normTheme(ui.theme));
      setAutoRefresh(ui.auto_refresh !== false);
      setBootstrapped(true);
      setDirty(false);
      onPreferencesApplied?.({
        theme: normTheme(ui.theme),
        auto_refresh: ui.auto_refresh !== false,
      });
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setBootstrapped(true);
    }
  }, [onPreferencesApplied]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!bootstrapped || !dirty) return;
    window.clearTimeout(debounceRef.current);
    setSaveState("saving");
    debounceRef.current = window.setTimeout(() => {
      void (async () => {
        try {
          const body: UserSettingsPayload = {
            privacy_mode: privacyMode,
            ui_preferences: { theme, auto_refresh: autoRefresh },
          };
          await webFetch("/user/settings", {
            method: "POST",
            body: JSON.stringify(body),
          });
          setSaveState("saved");
          setDirty(false);
          setErrorMsg(null);
          onPreferencesApplied?.({ theme, auto_refresh: autoRefresh });
          window.setTimeout(() => setSaveState("idle"), 2200);
        } catch (e) {
          setSaveState("error");
          setErrorMsg(e instanceof Error ? e.message : String(e));
        }
      })();
    }, 500);
    return () => window.clearTimeout(debounceRef.current);
  }, [privacyMode, theme, autoRefresh, dirty, bootstrapped, onPreferencesApplied]);

  const markDirty = () => setDirty(true);

  return (
    <section
      className={`rounded-xl border border-zinc-800 bg-zinc-950/80 px-4 py-4 shadow-lg transition-colors duration-200 ${
        compact ? "" : "lg:sticky lg:top-24"
      }`}
    >
      <div className="mb-3 flex items-center gap-2">
        <Settings2 className="h-4 w-4 text-sky-400" aria-hidden />
        <h2 className="text-sm font-medium text-zinc-200">Your settings</h2>
        <span className="ml-auto flex items-center gap-1.5 text-[10px] text-zinc-500">
          {saveState === "saving" ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin text-sky-400" aria-hidden />
              Saving…
            </>
          ) : saveState === "saved" ? (
            <span className="text-emerald-400/90">Saved</span>
          ) : saveState === "error" ? (
            <span className="text-rose-400/90">Failed</span>
          ) : null}
        </span>
      </div>

      <p className="mb-4 text-[11px] leading-relaxed text-zinc-500">
        Privacy mode and UI preferences persist per account. Changes save automatically after a short pause.
      </p>

      {errorMsg ? (
        <p className="mb-3 rounded-md border border-rose-500/30 bg-rose-950/40 px-2 py-1.5 text-[11px] text-rose-100">
          {errorMsg}
        </p>
      ) : null}

      <div className="space-y-4">
        <label className="block">
          <span className="mb-1 block text-[11px] font-medium text-zinc-400">Privacy mode</span>
          <select
            className="w-full rounded-lg border border-zinc-700 bg-black/50 px-2 py-2 text-xs text-zinc-100 outline-none transition hover:border-zinc-600 focus:border-sky-500/60"
            value={privacyMode}
            disabled={!bootstrapped}
            onChange={(e) => {
              setPrivacyMode(normPrivacy(e.target.value));
              markDirty();
            }}
          >
            <option value="standard">Standard — balanced screening</option>
            <option value="strict">Strict — elevate medium-confidence secrets</option>
            <option value="paranoid">Paranoid — local_stub only, strict PII</option>
          </select>
        </label>

        <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-zinc-800/90 bg-black/30 px-3 py-2 transition hover:border-zinc-700">
          <span className="text-[11px] text-zinc-300">Theme</span>
          <select
            className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-[11px] text-zinc-100"
            value={theme}
            disabled={!bootstrapped}
            onChange={(e) => {
              setTheme(normTheme(e.target.value));
              markDirty();
            }}
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        </label>

        <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-zinc-800/90 bg-black/30 px-3 py-2 transition hover:border-zinc-700">
          <span className="text-[11px] text-zinc-300">Auto-refresh snapshot</span>
          <input
            type="checkbox"
            className="h-4 w-4 accent-sky-500"
            checked={autoRefresh}
            disabled={!bootstrapped}
            onChange={(e) => {
              setAutoRefresh(e.target.checked);
              markDirty();
            }}
          />
        </label>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-zinc-800/80 pt-3 text-[10px] text-zinc-600">
        <span className="inline-flex items-center gap-1">
          <Save className="h-3 w-3 opacity-70" aria-hidden />
          Debounced save · 500ms
        </span>
        <button
          type="button"
          className="text-sky-400/90 underline-offset-2 hover:text-sky-300 hover:underline"
          onClick={() => void load()}
        >
          Reload from server
        </button>
      </div>
    </section>
  );
}
