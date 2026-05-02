const SEEDS = [
  "run dev task: fix this failing test",
  "analyze this problem and suggest next steps",
  "create a plan for shipping the current milestone",
  "review the repo and suggest improvements",
  "show memory",
  "show system status",
] as const;

/**
 * Lightweight typing hints — natural language only (Phase 48).
 */
export function getInputSuggestions(typed: string, limit = 4): string[] {
  const q = (typed || "").trim();
  if (q.length < 2) {
    return Array.from(SEEDS).slice(0, limit);
  }
  const low = q.toLowerCase();
  const out = (SEEDS as readonly string[]).filter(
    (s) =>
      s.toLowerCase().includes(low) ||
      (low.startsWith("run") && s.toLowerCase().startsWith(low)),
  );
  if (out.length) {
    return out.slice(0, limit);
  }
  if (low.includes("readme") || low.includes("read")) {
    return ["add a README section about installation", "update project documentation for new env vars"].slice(0, limit);
  }
  if (low.includes("test") || low.includes("fix")) {
    return ["run dev task: fix the failing tests", "analyze why tests are failing"].slice(0, limit);
  }
  return [`run dev task: ${q}`].slice(0, limit);
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
