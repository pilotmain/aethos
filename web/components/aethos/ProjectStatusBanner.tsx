"use client";

/**
 * AethOS status strip — driven by env; hide with NEXT_PUBLIC_AETHOS_HIDE_STATUS_BANNER=true
 * (legacy: NEXT_PUBLIC_NEXA_HIDE_STATUS_BANNER).
 */
export function ProjectStatusBanner() {
  const hideA = process.env.NEXT_PUBLIC_AETHOS_HIDE_STATUS_BANNER;
  const hideN = process.env.NEXT_PUBLIC_NEXA_HIDE_STATUS_BANNER;
  const hideRaw = (hideA ?? hideN ?? "").toString();
  if (hideRaw) {
    const v = hideRaw.toLowerCase();
    if (v === "1" || v === "true" || v === "yes") return null;
  }
  const text =
    process.env.NEXT_PUBLIC_AETHOS_STATUS_BANNER?.trim() ||
    process.env.NEXT_PUBLIC_NEXA_STATUS_BANNER?.trim() ||
    "AethOS — The Agentic Operating System · Experimental · Developer-first";

  return (
    <div
      className="flex items-center justify-center gap-2 border-b border-amber-500/25 bg-amber-500/[0.07] px-3 py-2 text-center text-[11px] leading-snug text-amber-100/90"
      role="status"
    >
      <span className="font-medium tracking-wide text-amber-200/95">{text}</span>
    </div>
  );
}
