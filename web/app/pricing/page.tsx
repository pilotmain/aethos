"use client";

import Link from "next/link";

const DEFAULT_API =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_AETHOS_API_BASE
    ? process.env.NEXT_PUBLIC_AETHOS_API_BASE.replace(/\/$/, "")
    : "";

export default function PricingPage() {
  const plans = [
    {
      name: "Free",
      price: "$0",
      description: "For individuals and small projects",
      features: ["1 agent", "10K tokens/month", "7-day history", "Community support"],
      cta: "Get Started",
      highlighted: false,
      tier: "free",
    },
    {
      name: "Pro",
      price: "$20",
      period: "/month",
      description: "For professionals and small teams",
      features: ["5 agents", "100K tokens/month", "30-day history", "Email support"],
      cta: "Subscribe",
      highlighted: true,
      tier: "pro",
    },
    {
      name: "Business",
      price: "$100",
      period: "/month",
      description: "For growing teams",
      features: ["25 agents", "1M tokens/month", "90-day history", "Priority support", "RBAC"],
      cta: "Contact Sales",
      highlighted: false,
      tier: "business",
    },
    {
      name: "Enterprise",
      price: "Custom",
      description: "For large organizations",
      features: [
        "Unlimited agents",
        "Unlimited tokens",
        "1-year history",
        "Dedicated support",
        "SSO",
        "SLA",
      ],
      cta: "Contact Sales",
      highlighted: false,
      tier: "enterprise",
    },
  ];

  const pricePro =
    typeof process !== "undefined" ? process.env.NEXT_PUBLIC_STRIPE_PRICE_ID_PRO?.trim() || "" : "";

  return (
    <div className="min-h-screen bg-zinc-950 px-4 py-16 text-zinc-100">
      <div className="mx-auto max-w-6xl">
        <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
          <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-300">
            ← Home
          </Link>
          <Link href="/dashboard/billing" className="text-sm text-emerald-400/90 hover:text-emerald-300">
            Billing dashboard →
          </Link>
        </div>
        <div className="mb-12 text-center">
          <h1 className="text-4xl font-bold text-white">Simple, Transparent Pricing</h1>
          <p className="mt-2 text-zinc-400">Choose the plan that works for you</p>
          {DEFAULT_API ? (
            <p className="mt-3 text-xs text-zinc-500">
              API base: <span className="font-mono text-zinc-400">{DEFAULT_API}</span>
            </p>
          ) : null}
        </div>

        <div className="grid gap-6 md:grid-cols-4">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`rounded-lg border p-6 ${
                plan.highlighted
                  ? "scale-[1.02] border-emerald-600/50 bg-zinc-900 shadow-lg shadow-emerald-950/40"
                  : "border-zinc-800 bg-zinc-900/60"
              }`}
            >
              <h3 className="text-xl font-bold text-white">{plan.name}</h3>
              <div className="mt-4">
                <span className="text-3xl font-bold">{plan.price}</span>
                {"period" in plan && plan.period ? (
                  <span className="text-sm text-zinc-400">{plan.period}</span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-zinc-400">{plan.description}</p>
              <ul className="mt-4 space-y-2 text-sm text-zinc-300">
                {plan.features.map((feature) => (
                  <li key={feature}>✓ {feature}</li>
                ))}
              </ul>
              <div className="mt-6">
                {plan.tier === "pro" && pricePro ? (
                  <Link
                    href="/dashboard/billing"
                    className="block w-full rounded-md bg-emerald-600 py-2 text-center text-sm font-medium text-white hover:bg-emerald-500"
                  >
                    {plan.cta}
                  </Link>
                ) : (
                  <button
                    type="button"
                    className="w-full rounded-md border border-zinc-700 bg-zinc-950 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-800"
                  >
                    {plan.cta}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        <p className="mt-12 text-center text-xs text-zinc-500">
          Hosted checkout uses{" "}
          <code className="font-mono text-zinc-400">POST /api/v1/billing/create-checkout</code> with a cloud bearer
          token. Configure{" "}
          <code className="font-mono text-zinc-400">NEXT_PUBLIC_STRIPE_PRICE_ID_PRO</code> for one-click upgrades from
          the billing page.
        </p>
      </div>
    </div>
  );
}
