"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { defaultConfig, readConfig, saveConfig } from "@/lib/config";
import {
  describeAethosWebUserIdProblem,
  USER_ID_REQUIRED_MSG,
  WEB_USER_ID_FIELD_HELP,
} from "@/lib/webUserId";

export default function LoginPage() {
  const router = useRouter();
  const c0 = readConfig();
  const [apiBase, setApiBase] = useState(c0.apiBase || defaultConfig.apiBase);
  const [userId, setUserId] = useState(c0.userId);
  const [token, setToken] = useState(c0.token);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [regenBusy, setRegenBusy] = useState(false);
  const [ssoReady, setSsoReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/setup-creds", { cache: "no-store" });
        const creds = (await r.json()) as { api_base?: string; user_id?: string; bearer_token?: string };
        if (cancelled) return;
        const ab = (creds.api_base || "").trim().replace(/\/$/, "");
        const uid = (creds.user_id || "").trim();
        const btok = (creds.bearer_token || "").trim();
        if (!ab && !uid && !btok) return;
        const cur = readConfig();
        const next = {
          apiBase: ab || cur.apiBase || defaultConfig.apiBase,
          userId: uid || cur.userId,
          token: btok || cur.token,
        };
        saveConfig(next);
        setApiBase(next.apiBase);
        setUserId(next.userId);
        setToken(next.token);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const sp = new URLSearchParams(window.location.search);
    const xuid = (sp.get("x_user_id") || "").trim();
    if (!xuid) return;
    const cur = readConfig();
    saveConfig({ ...cur, userId: xuid });
    setUserId(xuid);
    const url = new URL(window.location.href);
    url.searchParams.delete("x_user_id");
    window.history.replaceState({}, "", `${url.pathname}${url.search}`);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const base = (apiBase.trim() || defaultConfig.apiBase).replace(/\/$/, "");
    fetch(`${base}/api/v1/sso/status`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (cancelled || !j || typeof j !== "object") return;
        setSsoReady(Boolean((j as { sso_enabled?: boolean }).sso_enabled));
      })
      .catch(() => {
        if (!cancelled) setSsoReady(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  const trimmedUserId = userId.trim();
  const userIdProblem =
    !trimmedUserId && submitAttempted
      ? USER_ID_REQUIRED_MSG
      : trimmedUserId
        ? describeAethosWebUserIdProblem(userId)
        : null;
  const userIdInvalid = Boolean(userIdProblem);

  async function readErrorDetail(response: Response): Promise<string> {
    const text = await response.text();
    if (!text.trim()) {
      return response.statusText;
    }
    try {
      const body = JSON.parse(text) as { detail?: unknown };
      if (typeof body.detail === "string") {
        return body.detail;
      }
    } catch {
      /* keep text */
    }
    return text.length > 220 ? `${text.slice(0, 220)}…` : text;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitAttempted(true);
    setError(null);
    setSaved(false);
    if (!trimmedUserId) return;
    if (describeAethosWebUserIdProblem(userId)) return;
    const nextApiBase = apiBase.trim();
    const nextUserId = userId.trim();
    const nextToken = token.trim();
    setIsTesting(true);
    try {
      const base = (nextApiBase.trim() || defaultConfig.apiBase).replace(/\/$/, "");
      const headers: Record<string, string> = {
        Accept: "application/json",
        "X-User-Id": nextUserId,
      };
      if (nextToken) {
        headers.Authorization = `Bearer ${nextToken}`;
      }

      let response: Response;
      try {
        response = await fetch(`${base}/api/v1/health`, {
          headers,
          cache: "no-store",
        });
      } catch {
        throw new Error(`Cannot reach API at ${base}. Make sure the API is running and CORS allows this origin.`);
      }

      if (!response.ok) {
        const detail = await readErrorDetail(response);
        if (response.status === 401) {
          throw new Error(
            /bearer/i.test(detail)
              ? "Invalid bearer token. Check that it matches NEXA_WEB_API_TOKEN in the API environment."
              : `Unauthorized: ${detail}`,
          );
        }
        throw new Error(`Connection failed (${response.status}): ${detail || response.statusText}`);
      }

      saveConfig({ apiBase: nextApiBase, userId: nextUserId, token: nextToken });
      setSaved(true);
      router.push("/mission-control/overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection test failed.");
    } finally {
      setIsTesting(false);
    }
  }

  async function regenerateToken() {
    setError(null);
    const base = (apiBase.trim() || defaultConfig.apiBase).replace(/\/$/, "");
    const nextUserId = userId.trim();
    if (!nextUserId) {
      setError("Enter your user id before rotating the token.");
      return;
    }
    setRegenBusy(true);
    try {
      const headers: Record<string, string> = {
        Accept: "application/json",
        "X-User-Id": nextUserId,
      };
      if (token.trim()) {
        headers.Authorization = `Bearer ${token.trim()}`;
      }
      const res = await fetch(`${base}/api/v1/user/regenerate-token`, {
        method: "POST",
        headers,
        cache: "no-store",
      });
      if (!res.ok) {
        const detail = await readErrorDetail(res);
        throw new Error(detail || res.statusText);
      }
      const data = (await res.json()) as { token?: string };
      const nextTok = (data.token || "").trim();
      if (!nextTok) {
        throw new Error("Server did not return a token.");
      }
      setToken(nextTok);
      saveConfig({ apiBase: base, userId: nextUserId, token: nextTok });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Token rotation failed.");
    } finally {
      setRegenBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-8 text-zinc-100">
      <div className="mx-auto max-w-md">
        <a href="/" className="mb-4 text-xs text-zinc-500 hover:text-zinc-300">
          ← Back to app
        </a>
        <h1 className="text-xl font-semibold text-white">Connection settings</h1>
        <p className="mt-2 text-sm text-zinc-400">Configure how this browser connects to your AethOS API.</p>
        <p className="mt-2 text-sm text-zinc-400">
          The API may require <code className="text-emerald-400/90">NEXA_WEB_API_TOKEN</code> and this browser must
          send the same value as <code className="font-mono text-zinc-300">Authorization: Bearer</code> when set.
          Your <code className="text-zinc-300">X-User-Id</code> is your AethOS account id from Telegram (
          <code className="text-zinc-300">tg_…</code>), email channel (<code className="text-zinc-300">em_…</code>),
          Slack (<code className="text-zinc-300">slack_…</code>), SMS, WhatsApp, Apple Messages, or a{" "}
          <code className="text-zinc-300">web_</code>/<code className="text-zinc-300">local_</code> id (the setup
          wizard stores <code className="text-zinc-300">TEST_X_USER_ID</code>, often{" "}
          <code className="text-zinc-300">web_setup_…</code>).
        </p>
        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-500">API base URL</span>
            <input
              className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-zinc-100"
              value={apiBase}
              onChange={(e) => setApiBase(e.target.value)}
              autoComplete="off"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-500">User id (X-User-Id)</span>
            <input
              className={`rounded-md border bg-zinc-900 px-3 py-2 text-zinc-100 ${
                userIdInvalid ? "border-rose-500/60" : "border-zinc-800"
              }`}
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="web_setup_… or tg_123456789 or em_…"
              autoComplete="off"
              aria-invalid={userIdInvalid}
              aria-describedby={userIdInvalid ? "user-id-error" : "user-id-help"}
            />
            <span id="user-id-help" className="text-[11px] leading-relaxed text-zinc-500">
              {WEB_USER_ID_FIELD_HELP}
            </span>
            {userIdProblem && (
              <p id="user-id-error" role="alert" className="text-[12px] text-rose-400">
                {userIdProblem}
              </p>
            )}
          </label>
          {ssoReady && (
            <div className="rounded-md border border-violet-500/25 bg-violet-950/40 px-3 py-3">
              <p className="text-xs leading-relaxed text-violet-100/90">
                OIDC SSO is enabled on this API. You will authenticate at your identity provider, then return here with{" "}
                <code className="text-zinc-200">X-User-Id</code> prefilled. If the API uses{" "}
                <code className="text-zinc-200">NEXA_WEB_API_TOKEN</code>, paste or regenerate the bearer token below.
              </p>
              <button
                type="button"
                className="mt-2 w-full rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
                onClick={() => {
                  const base = (apiBase.trim() || defaultConfig.apiBase).replace(/\/$/, "");
                  window.location.href = `${base}/api/v1/sso/login`;
                }}
              >
                Login with SSO
              </button>
            </div>
          )}
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-zinc-500">Bearer token (optional)</span>
            <input
              className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-zinc-100"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              type="password"
              autoComplete="off"
              placeholder="matches NEXA_WEB_API_TOKEN"
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void regenerateToken()}
              disabled={regenBusy || isTesting}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {regenBusy ? "Rotating…" : "Regenerate API token"}
            </button>
            <span className="text-[11px] text-zinc-500">
              Writes a new <code className="text-zinc-400">NEXA_WEB_API_TOKEN</code> to the API{" "}
              <code className="text-zinc-400">.env</code> (requires wizard user or owner).
            </span>
          </div>
          {error && (
            <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200" role="alert">
              {error}
            </div>
          )}
          {saved && (
            <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200" role="status">
              Settings saved.
            </div>
          )}
          <button
            type="submit"
            disabled={isTesting}
            className="mt-2 rounded-md bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isTesting ? "Testing..." : "Save & Test Connection"}
          </button>
        </form>
      </div>
    </div>
  );
}
