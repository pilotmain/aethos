"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { defaultConfig, readConfig, saveConfig } from "@/lib/config";
import {
  describeNexaWebUserIdProblem,
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

  const trimmedUserId = userId.trim();
  const userIdProblem =
    !trimmedUserId && submitAttempted
      ? USER_ID_REQUIRED_MSG
      : trimmedUserId
        ? describeNexaWebUserIdProblem(userId)
        : null;
  const userIdInvalid = Boolean(userIdProblem);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitAttempted(true);
    if (!trimmedUserId) return;
    if (describeNexaWebUserIdProblem(userId)) return;
    saveConfig({ apiBase: apiBase.trim(), userId: userId.trim(), token: token.trim() });
    router.push("/");
  }

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-8 text-zinc-100">
      <div className="mx-auto max-w-md">
        <a href="/" className="mb-4 text-xs text-zinc-500 hover:text-zinc-300">
          ← Back to app
        </a>
        <h1 className="text-xl font-semibold text-white">Connection settings</h1>
        <p className="mt-2 text-sm text-zinc-400">Configure how this browser connects to your Nexa API.</p>
        <p className="mt-2 text-sm text-zinc-400">
          The API may require <code className="text-emerald-400/90">NEXA_WEB_API_TOKEN</code> and this browser must
          send the same value as <code className="font-mono text-zinc-300">Authorization: Bearer</code> when set.
          Your <code className="text-zinc-300">X-User-Id</code> is your Nexa account id from Telegram (
          <code className="text-zinc-300">tg_…</code>), email channel (<code className="text-zinc-300">em_…</code>),
          Slack (<code className="text-zinc-300">slack_…</code>), SMS, WhatsApp, Apple Messages, or a{" "}
          <code className="text-zinc-300">web_</code>/<code className="text-zinc-300">local_</code> id.
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
              placeholder="tg_123456789 or em_… or slack_U01…"
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
          <button
            type="submit"
            className="mt-2 rounded-md bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 hover:bg-white"
          >
            Save
          </button>
        </form>
      </div>
    </div>
  );
}
