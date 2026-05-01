"use client";

/**
 * Nexa Next status strip — driven by env; hide with NEXT_PUBLIC_NEXA_HIDE_STATUS_BANNER=true.
 */
export function ProjectStatusBanner() {
  if (typeof process.env.NEXT_PUBLIC_NEXA_HIDE_STATUS_BANNER === "string") {
    const v = process.env.NEXT_PUBLIC_NEXA_HIDE_STATUS_BANNER.toLowerCase();
    if (v === "1" || v === "true" || v === "yes") return null;
  }
  const text =
    process.env.NEXT_PUBLIC_NEXA_STATUS_BANNER?.trim() ||
    "Nexa Next — Experimental · Developer-first · Privacy-first architecture";

  return (
    <div
      className="flex items-center justify-center gap-2 border-b border-amber-500/25 bg-amber-500/[0.07] px-3 py-2 text-center text-[11px] leading-snug text-amber-100/90"
      role="status"
    >
      <span className="font-medium tracking-wide text-amber-200/95">{text}</span>
    </div>
  );
}
