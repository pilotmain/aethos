/** Pure helpers for Trust / Activity channel badges and client-side filters (Phase 5). */

export type TrustChannelTab = "all" | "web" | "telegram" | "system";

/** Short label for activity cards; unknown / missing → System (internal or legacy audits). */
export function channelBadgeLabel(channel: string | null | undefined): string {
  const c = (channel ?? "").trim().toLowerCase();
  if (c === "web") return "Web";
  if (c === "telegram") return "Telegram";
  return "System";
}

export function matchesChannelFilter(
  channel: string | null | undefined,
  tab: TrustChannelTab
): boolean {
  if (tab === "all") return true;
  const c = (channel ?? "").trim().toLowerCase();
  if (tab === "web") return c === "web";
  if (tab === "telegram") return c === "telegram";
  if (tab === "system") return !c;
  return true;
}
