/**
 * Authenticated JSON client — wraps the shared web helper (X-User-Id + bearer from Login → Connection).
 *
 * Pass `signal` in `RequestInit` to cancel in-flight requests (same signature as `fetch`).
 */
export { webFetch as apiFetch, webFetch as fetchAPI } from "@/lib/api";
export type { ApiOptions } from "@/lib/api";
export { DEFAULT_API_BASE, DEFAULT_API_BASE as API_BASE, readConfig } from "@/lib/config";
