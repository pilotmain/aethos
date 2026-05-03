# NEXA_DYNAMIC_ROUTING_AND_FOCUS_V2_HANDOFF.md

**Title:** Nexa Dynamic Provider Routing + Strict Focus Discipline (V2)  
**Version:** 2.0  
**Status:** Implemented — see `provider_router.py`, `intent_focus_filter.py`, `external_execution_session.py`

## What changed

- **Provider scores** — Neutral `generic` baseline **0.2**; URL-first boosts for **Vercel**, **Railway**, **GitHub**, **AWS** (`.amazonaws.com`, `aws.amazon.com`, keywords). `detect_primary_provider` logs **`provider_router.dynamic_detected`**.
- **Operator hints** — GitHub- or AWS-dominant turns can clear **Railway** hints; **AWS** hint added in `detect_provider_hints`.
- **`should_skip_railway_bounded_path`** — Also true for **GitHub**- or **AWS**-dominant messages (not only Vercel).
- **Focus intent** — `ignore_railway` when user asked **GitHub push** or **AWS** scope without naming Railway.
- **Reply scrub** — `strip_unrelated_providers_from_reply` removes lines hawking providers the router says the user did not ask for (skips bodies containing code fences).
- **External execution resume** — Stores **`detected_provider`** on `collected`; follow-up questions and **probe intro** use **Vercel-aware** neutral copy; **empty investigation** still yields a visible italic line (no silent ACK).
- **Railway credential reply** — Opens with **“Key received”** (still secure, no echo).

## Not done (by design)

- **No global 180-character truncation** of operator/execution replies — that would destroy command evidence and progress blocks.
- **No `confidence < 0.7` hard blocker** returning a dict — kept sync `ExecutionLoopResult` / `OperatorExecutionResult` flows.

## Tests

- `tests/test_dynamic_routing_v2.py`
- Existing routing/focus/external-exec tests still pass.

---

*End of handoff.*
