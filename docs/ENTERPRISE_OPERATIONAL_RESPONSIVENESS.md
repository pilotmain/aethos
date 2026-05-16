# Enterprise operational responsiveness (Step 13)

Step 13 builds on Step 12 incremental hydration with:

1. **Payload discipline** — truth stays under `AETHOS_TRUTH_PAYLOAD_MAX_BYTES`
2. **Timeline windows** — paged `/timeline/window` instead of full history
3. **Worker summaries** — paginated `/runtime/workers/summaries`
4. **Memory sweeps** — throttled pruning during hydration maintenance
5. **Enterprise views** — `enterprise_operational_views` on truth for Office and insights

Mission Control should poll slice APIs and windowed timelines rather than full truth on every refresh.
