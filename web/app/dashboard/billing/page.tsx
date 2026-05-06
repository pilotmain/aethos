"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { defaultConfig, readConfig } from "@/lib/config";

const CLOUD_TOKEN_KEY = "aethos_cloud_access_token";

type SubscriptionJson = {
  tier?: string;
  status?: string;
  end_date?: string | null;
};

type UsageJson = {
  tokens_used?: number;
  token_limit?: number;
  percentage?: number;
  api_calls?: number;
};

export default function BillingDashboardPage() {
  const [subscription, setSubscription] = useState<SubscriptionJson | null>(null);
  const [usage, setUsage] = useState<UsageJson | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tokenPresent, setTokenPresent] = useState(false);

  const apiBase = (readConfig().apiBase || defaultConfig.apiBase).replace(/\/$/, "");
  const pricePro =
    typeof process !== "undefined" ? process.env.NEXT_PUBLIC_STRIPE_PRICE_ID_PRO?.trim() || "" : "";

  const loadBillingData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token =
        typeof window !== "undefined" ? window.localStorage.getItem(CLOUD_TOKEN_KEY)?.trim() || "" : "";
      setTokenPresent(Boolean(token));
      if (!token) {
        setSubscription(null);
        setUsage(null);
        return;
      }
      const headers: HeadersInit = {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      };
      const [subRes, usageRes] = await Promise.all([
        fetch(`${apiBase}/api/v1/billing/subscription`, { headers }),
        fetch(`${apiBase}/api/v1/billing/usage`, { headers }),
      ]);
      if (!subRes.ok) {
        const body = await subRes.text();
        throw new Error(body || `subscription HTTP ${subRes.status}`);
      }
      if (!usageRes.ok) {
        const body = await usageRes.text();
        throw new Error(body || `usage HTTP ${usageRes.status}`);
      }
      setSubscription((await subRes.json()) as SubscriptionJson);
      setUsage((await usageRes.json()) as UsageJson);
    } catch (e) {
      console.error(e);
      setError(e instanceof Error ? e.message : "Failed to load billing data");
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    void loadBillingData();
  }, [loadBillingData]);

  async function handleUpgrade() {
    const token =
      typeof window !== "undefined" ? window.localStorage.getItem(CLOUD_TOKEN_KEY)?.trim() || "" : "";
    if (!pricePro) {
      setError("Set NEXT_PUBLIC_STRIPE_PRICE_ID_PRO for checkout.");
      return;
    }
    const res = await fetch(`${apiBase}/api/v1/billing/create-checkout`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        price_id: pricePro,
        success_url: typeof window !== "undefined" ? window.location.href : "",
        cancel_url: typeof window !== "undefined" ? window.location.href : "",
      }),
    });
    if (!res.ok) {
      const t = await res.text();
      setError(t || `checkout HTTP ${res.status}`);
      return;
    }
    const data = (await res.json()) as { checkout_url?: string };
    if (data.checkout_url && typeof window !== "undefined") {
      window.location.href = data.checkout_url;
    }
  }

  async function handleManageSubscription() {
    const token =
      typeof window !== "undefined" ? window.localStorage.getItem(CLOUD_TOKEN_KEY)?.trim() || "" : "";
    const res = await fetch(`${apiBase}/api/v1/billing/create-portal`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        return_url: typeof window !== "undefined" ? window.location.href : "",
      }),
    });
    if (!res.ok) {
      const t = await res.text();
      setError(t || `portal HTTP ${res.status}`);
      return;
    }
    const data = (await res.json()) as { portal_url?: string };
    if (data.portal_url && typeof window !== "undefined") {
      window.location.href = data.portal_url;
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 px-4 py-16 text-zinc-100">
        <p className="text-zinc-400">Loading…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-10 text-zinc-100">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <Link href="/pricing" className="text-sm text-zinc-500 hover:text-zinc-300">
            ← Pricing
          </Link>
          <button
            type="button"
            onClick={() => loadBillingData()}
            className="text-sm text-emerald-400/90 hover:text-emerald-300"
          >
            Refresh
          </button>
        </div>

        <h1 className="text-2xl font-bold text-white">Billing</h1>
        <p className="mt-2 text-sm text-zinc-400">Manage your subscription and usage (AethOS Cloud).</p>

        {!tokenPresent ? (
          <div className="mt-8 rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
            <p className="text-sm text-zinc-300">
              No cloud bearer token found. Store a JWT from{" "}
              <code className="font-mono text-emerald-400/90">POST /api/v1/saas/auth/register</code> or{" "}
              <code className="font-mono text-emerald-400/90">…/login</code> in{" "}
              <code className="font-mono text-zinc-400">localStorage</code> as{" "}
              <code className="font-mono text-zinc-400">{CLOUD_TOKEN_KEY}</code>, or continue with header-based auth from{" "}
              <Link href="/login" className="text-emerald-400/90 hover:text-emerald-300">
                Connection settings
              </Link>
              .
            </p>
          </div>
        ) : null}

        {error ? (
          <div className="mt-6 rounded-md border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        <div className="mt-8 rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Current Plan</h2>
              <p className="mt-2 text-3xl font-bold capitalize text-white">{subscription?.tier ?? "—"}</p>
              <p className="mt-1 text-sm text-zinc-400">
                {subscription?.status === "active" ? "Active" : subscription?.status ?? "—"}
              </p>
            </div>
            <button
              type="button"
              onClick={() => void handleManageSubscription()}
              className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              Manage Subscription
            </button>
          </div>
        </div>

        <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
          <h2 className="text-lg font-semibold text-white">Current Usage</h2>
          <div className="mt-4 space-y-4">
            <div>
              <div className="mb-1 flex justify-between text-sm text-zinc-400">
                <span>Tokens Used</span>
                <span>
                  {(usage?.tokens_used ?? 0).toLocaleString()} / {(usage?.token_limit ?? 0).toLocaleString()}
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-zinc-800">
                <div
                  className="h-2 rounded-full bg-emerald-600"
                  style={{ width: `${Math.min(100, usage?.percentage ?? 0)}%` }}
                />
              </div>
            </div>
            <div className="flex justify-between text-sm text-zinc-400">
              <span>API Calls (month)</span>
              <span>{(usage?.api_calls ?? 0).toLocaleString()}</span>
            </div>
          </div>
        </div>

        {subscription?.tier === "free" ? (
          <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/60 p-6">
            <h2 className="text-lg font-semibold text-white">Upgrade to Pro</h2>
            <p className="mt-2 text-sm text-zinc-400">Higher limits and email support.</p>
            <button
              type="button"
              onClick={() => void handleUpgrade()}
              className="mt-4 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
            >
              Upgrade Now
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
