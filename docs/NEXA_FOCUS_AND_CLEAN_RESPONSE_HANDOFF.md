# NEXA_FOCUS_AND_CLEAN_RESPONSE_HANDOFF.md

**Title:** Nexa Focus & Clean Response Discipline  
**Version:** 1.0  
**Status:** Implemented — see `app/services/intent_focus_filter.py`

## Summary

- **`extract_focused_intent`** — Detects Vercel / GitHub / explicit Railway scope; sets **`ignore_railway`** when the user named Vercel (or Vercel-like URLs) but not Railway.
- **Operator loop** — Clears the Railway hint when `ignore_railway` so the Railway-only deferral path does not run.
- **Execution loop** — Skips the bounded Railway runner when `ignore_railway` **or** existing `should_skip_railway_bounded_path`.
- **`text_has_railway_execution_context`** — Returns **False** when `ignore_railway` so CLI probes do not start on pure Vercel turns.
- **Gateway** — `gateway_finalize_operator_or_execution_reply` runs **`apply_focus_discipline_to_operator_execution_text`**: drops lines that mention Railway without Vercel on the same line, and compresses long “once access is in place” style blocks for Vercel/GitHub-focused asks.

## Tests

`tests/test_focused_response.py`

---

*End of handoff.*
