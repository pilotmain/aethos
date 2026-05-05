/**
 * Authenticated JSON client — wraps the shared web helper (X-User-Id + bearer from Login → Connection).
 *
 * Pass `signal` in `RequestInit` to cancel in-flight requests (same signature as `fetch`).
 */
export { webFetch as apiFetch } from "@/lib/api";
export { DEFAULT_API_BASE, readConfig } from "@/lib/config";
