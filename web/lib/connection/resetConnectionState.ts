/**
 * Clear saved connection/auth/session keys so the user can reconnect cleanly.
 * Preserves non-sensitive UI preferences (theme, appearance).
 */

/** Keys to keep when resetting (must match product naming). */
export const CONNECTION_RESET_KEEP_KEYS = new Set([
  "nexa-theme",
  "nexa-appearance",
]);

export function resetConnectionState(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    for (const key of Object.keys(window.localStorage)) {
      if (!CONNECTION_RESET_KEEP_KEYS.has(key)) {
        window.localStorage.removeItem(key);
      }
    }
    window.sessionStorage.clear();
  } catch {
    /* ignore quota / private mode */
  }
}
