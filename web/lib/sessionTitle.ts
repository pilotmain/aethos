/** Derive a short web chat session title from the first user message (no LLM). */
export function deriveSessionTitleFromMessage(text: string): string {
  let t = (text || "").trim();
  t = t.replace(/^@(\w+)\s+/, "");
  const words = t.split(/\s+/).filter(Boolean).slice(0, 10);
  t = words.join(" ");
  if (t.length > 40) {
    t = `${t.slice(0, 37)}…`;
  }
  return t || "New chat";
}
