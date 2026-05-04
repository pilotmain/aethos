/**
 * Classify browser/API errors for recovery UX (network vs auth vs other).
 */

export function isAuthFailureError(message: string): boolean {
  const m = (message || "").trim();
  if (/^401\b/.test(m) || /^403\b/.test(m)) return true;
  if (/Unauthorized/i.test(m) || /Forbidden/i.test(m)) return true;
  return false;
}

export function isUnreachableApiError(message: string): boolean {
  const m = (message || "").trim();
  if (/Cannot reach API/i.test(m)) return true;
  if (/Failed to fetch/i.test(m)) return true;
  if (/NetworkError/i.test(m)) return true;
  if (/Load failed/i.test(m)) return true;
  return false;
}
