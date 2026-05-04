"use client";

import Link from "next/link";
import { applyApiBaseAndReload } from "@/lib/config";
import { isAuthFailureError } from "@/lib/connection/classifyWebError";
import { portFromApiBase } from "@/lib/connection/portHint";
import { resetConnectionState } from "@/lib/connection/resetConnectionState";
import type { ConnectionDiagnosis } from "@/lib/connection/types";

type Props = {
  /** Raw error (used for classification). */
  dataError: string;
  /** Optional friendlier line for display (e.g. Mission Control formatting). */
  errorDisplay?: string;
  diagnosis: ConnectionDiagnosis | null;
  onRetry: () => void;
  /** When true, use compact inline variant (e.g. Mission Control header). */
  compact?: boolean;
};

/**
 * Distinguishes unreachable API, wrong saved API base, and stale session — with recovery actions.
 */
export function ConnectionErrorRecovery({
  dataError,
  errorDisplay,
  diagnosis,
  onRetry,
  compact = false,
}: Props) {
  const displayText = errorDisplay ?? dataError;
  const sessionStale = isAuthFailureError(dataError) && (diagnosis?.healthReachable ?? false);
  const showPortSwitch = Boolean(
    diagnosis?.alternateReachable && diagnosis.suggestedApiBase && !diagnosis.healthReachable
  );
  const savedPort = diagnosis ? portFromApiBase(diagnosis.apiBase) : "";
  const suggestedPort = diagnosis?.suggestedApiBase
    ? portFromApiBase(diagnosis.suggestedApiBase)
    : "";
  const isServerError = /^5\d\d:/.test((dataError || "").trim());
  const showStaleStateHint =
    !sessionStale &&
    !showPortSwitch &&
    Boolean(diagnosis?.healthReachable) &&
    !isServerError;

  function onReset() {
    resetConnectionState();
    window.location.reload();
  }

  if (compact) {
    return (
      <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-start">
        <p className="min-w-0 flex-1 [overflow-wrap:anywhere] break-words">{displayText}</p>
        <div className="flex flex-wrap gap-1">
          <button
            type="button"
            className="shrink-0 rounded border border-rose-400/50 px-2 py-1 text-[11px] hover:bg-white/5"
            onClick={onRetry}
          >
            Retry
          </button>
          {showPortSwitch && diagnosis?.suggestedApiBase ? (
            <button
              type="button"
              className="shrink-0 rounded border border-amber-400/50 bg-amber-950/40 px-2 py-1 text-[11px] text-amber-50 hover:bg-amber-900/50"
              onClick={() => applyApiBaseAndReload(diagnosis.suggestedApiBase!)}
            >
              Switch to {suggestedPort || "suggested API"}
            </button>
          ) : null}
          <button
            type="button"
            className="shrink-0 rounded border px-2 py-1 text-[11px] hover:bg-white/5"
            onClick={onReset}
          >
            Reset state
          </button>
          <Link
            href="/login"
            className="shrink-0 rounded border border-zinc-500/40 px-2 py-1 text-[11px] hover:bg-white/5"
          >
            Login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-4 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-amber-100/90">
      <p className="font-medium text-amber-50">Could not load Nexa data. Check API base URL or login settings.</p>

      {sessionStale ? (
        <p className="mt-2 text-amber-100/95">
          API is reachable, but your login/session looks stale. Update your user id or bearer token in Connection
          settings.
        </p>
      ) : null}

      {showPortSwitch && diagnosis?.suggestedApiBase ? (
        <p className="mt-2 text-amber-100/90">
          Your browser is using API base <span className="font-mono">{diagnosis.apiBase}</span>
          {savedPort ? <> (port {savedPort})</> : null}. Another endpoint responds on{" "}
          <span className="font-mono">{diagnosis.suggestedApiBase}</span>
          {suggestedPort ? <> (port {suggestedPort})</> : null}.
        </p>
      ) : null}

      {!sessionStale && !showPortSwitch && diagnosis?.healthReachable && showStaleStateHint ? (
        <p className="mt-2 text-amber-100/90">
          Your API is reachable, but your saved browser connection state may be stale. Try resetting local connection
          state, then sign in again if needed.
        </p>
      ) : null}

      <p className="mt-1 break-words text-amber-200/70">{displayText}</p>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md bg-amber-500/20 px-3 py-1.5 text-xs text-amber-100 hover:bg-amber-500/30"
        >
          Retry
        </button>
        {showPortSwitch && diagnosis?.suggestedApiBase ? (
          <button
            type="button"
            onClick={() => applyApiBaseAndReload(diagnosis.suggestedApiBase!)}
            className="rounded-md border border-amber-400/40 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-50 hover:bg-amber-500/20"
          >
            Switch to {suggestedPort || "working API base"}
          </button>
        ) : null}
        <button
          type="button"
          onClick={onReset}
          className="rounded-md border border-amber-500/30 px-3 py-1.5 text-xs text-amber-100 hover:bg-amber-500/15"
        >
          Reset connection state
        </button>
        <Link
          href="/login"
          className="inline-flex items-center rounded-md border border-zinc-500/40 px-3 py-1.5 text-xs text-zinc-200 hover:bg-white/5"
        >
          {sessionStale ? "Sign in again" : "Open connection settings"}
        </Link>
      </div>
    </div>
  );
}
