const SEEDS = [
  "run dev: fix failing tests in the test suite",
  "run mission: ship the current milestone",
  "run dev: review the repo and suggest improvements",
  "create agent: API documentation reviewer",
  "show memory",
  "show system status",
] as const;

/**
 * When the user is typing, suggest a few dev / mission phrases (lightweight, no network).
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
    return ["run dev: fix the failing tests", "run dev: run tests and report"].slice(0, limit);
  }
  return [`run dev: ${q}`].slice(0, limit);
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
