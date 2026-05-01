const SEEDS = [
  "@dev add a README section about installation",
  "@dev fix failing tests in the test suite",
  "@dev update project documentation for new env vars",
  "@dev refactor duplicate code in services",
  "@ops list recent dev jobs",
  "@ops show worker status",
  "@dev status",
  "/help",
] as const;

/**
 * When the user is typing, suggest a few @dev / @ops / slash commands (lightweight, no network).
 */
export function getInputSuggestions(typed: string, limit = 4): string[] {
  const q = (typed || "").trim();
  if (q.length < 2) {
    return Array.from(SEEDS).slice(0, limit);
  }
  const low = q.toLowerCase();
  const out = (SEEDS as readonly string[]).filter(
    (s) => s.toLowerCase().includes(low) || (low.startsWith("@") && s.toLowerCase().startsWith(low)),
  );
  if (out.length) {
    return out.slice(0, limit);
  }
  if (low.includes("readme") || low.includes("read")) {
    return ["@dev add README note", "@dev create README section", "@dev update documentation"].slice(0, limit);
  }
  if (low.includes("test") || low.includes("fix")) {
    return ["@dev fix the failing tests", "@dev run tests and report"].slice(0, limit);
  }
  return ["@dev " + q].slice(0, limit);
}

export function jobNeedsBadge(status: string): { label: string; tone: "emerald" | "amber" | "zinc" | "rose" } {
  if (["completed", "succeeded", "success"].some((s) => status === s)) {
    return { label: "Done", tone: "emerald" };
  }
  if (["failed", "cancelled", "canceled", "error"].some((s) => status === s)) {
    return { label: "Failed", tone: "rose" };
  }
  if (["running", "processing", "queued", "needs_approval", "needs_risk_approval", "waiting_approval"].some((s) => status === s)) {
    return { label: "In progress", tone: "amber" };
  }
  return { label: status || "—", tone: "zinc" };
}
