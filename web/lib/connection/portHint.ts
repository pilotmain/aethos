/** Extract display port from an origin URL, or "". */
export function portFromApiBase(base: string): string {
  try {
    const u = new URL(base);
    return u.port || (u.protocol === "https:" ? "443" : "80");
  } catch {
    return "";
  }
}
