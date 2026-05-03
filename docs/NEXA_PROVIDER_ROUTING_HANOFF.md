# NEXA_PROVIDER_ROUTING_HANOFF.md

**Title:** Robust Provider Intent Routing for Operator / Execution Loop  
**Version:** 1.0 (fixes the Vercel → Railway misroute)  
**Status:** Implemented in-repo — see `app/services/provider_router.py`  
**Goal:** Make Nexa’s gateway + brain reliably detect the correct provider (Vercel, Railway, GitHub, generic) from user intent and URLs **before** any preferences recording or runner selection.

---

## 1. Why this handoff exists

The bug:

- User said “go to vercel.com” + gave a Vercel URL.
- Nexa still recorded “Railway/deploy preferences” and talked about Railway.

Root cause: Provider detection was too weak / late; `https://` plus external-exec heuristics treated the turn as “hosted” and the **Railway** bounded path was the default.

---

## 2. Implementation summary

| Piece | Role |
|--------|------|
| `app/services/provider_router.py` | `extract_urls_from_text`, `detect_primary_provider`, `apply_router_to_operator_hints`, `should_skip_railway_bounded_path`, `format_provider_clarification_blocker` |
| `operator_execution_loop.py` | Merges router output after `detect_provider_hints` so Vercel-dominant turns clear `railway`. |
| `execution_loop.py` | Skips bounded Railway investigation when `should_skip_railway_bounded_path`; neutral “deploy/hosted” copy on resume. |
| `external_execution_session.py` | `text_has_railway_execution_context` returns false for Vercel-dominant turns; follow-up ack uses “hosted” wording. |
| `operator_runners/base.py` | `detect_provider_hints` also treats `vercel.com` in text as a Vercel cue. |

Explicit **Railway** mentions (keyword + strong Railway score / domain) **do not** skip the Railway path.

---

## 3. Tests

`tests/test_provider_routing.py` — URL extraction, scores, tie → generic, skip Railway for Vercel-only, operator turn prefers Vercel.

---

*End of handoff.*
