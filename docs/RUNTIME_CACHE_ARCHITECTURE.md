# Runtime cache architecture

Two layers:

1. **Full truth** — `mc_runtime_truth_cache` in `aethos.json`, keyed by user (`_global` when anonymous). TTL: `AETHOS_TRUTH_CACHE_TTL_SEC`.
2. **Slices** — `mc_runtime_slice_cache`, per-user buckets per slice name. TTL: `AETHOS_TRUTH_SLICE_TTL_SEC`. API slices use a 10s TTL via `get_lightweight_slice()`.

Invalidation:

- `invalidate_runtime_truth_cache(user_id?)` — full truth.
- `invalidate_slice_cache(user_id?, slice_name?)` — slices + cascaded full-truth invalidation.

Tracked metrics: `hydration_metrics`, `runtime_discipline_metrics.truth_cache_*`, and truth keys `runtime_performance` / `hydration_metrics`.
