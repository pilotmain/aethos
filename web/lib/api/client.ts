/**
 * Authenticated JSON client — wraps the shared web helper (X-User-Id + bearer from Login → Connection).
 */
export { webFetch as apiFetch } from "@/lib/api";
export { DEFAULT_API_BASE, readConfig } from "@/lib/config";
