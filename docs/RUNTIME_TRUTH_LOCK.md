# Runtime truth lock (Phase 3 Step 16)

Runtime truth is the **single operational authority**:

```
build_runtime_truth() → hydrate_runtime_truth_incremental() → summarize_truth_payload
```

`truth_lock` on truth validates required keys and warns on fragmentation.

API: `GET /mission-control/runtime/truth-lock`

Deprecated paths: see `cleanup_completion.deprecated_runtime_paths` and `docs/RUNTIME_DEPRECATIONS.md`.
