# Nexa enhanced orchestration — Phase 2 (OpenClaw-style chat magic)

**Status:** Implemented in-repo (chat-only slice; no Mission Control streaming).  
**Related:** `docs/NEXA_ENHANCED_ORCHESTRATION_SPEC.md`, `~/.aethos/docs/handoffs/HANDOFF_OPERATOR_EXECUTION_AND_ORCHESTRATION.md` (local handoff pack).

---

## Product intent

- **PULSE.md:** Re-read on every operator turn (lightweight file read; no cache).
- **Live progress:** Short step lines before each action (inspect → pulse → patch → tests → commit → deploy → verify).
- **Truth:** No “fixed / deployed / healthy / mission complete” without strict proof (deploy + HTTP verify in 2xx when deploy ran).
- **PULSE → deploy skip:** When standing orders clearly forbid production deploy, skip the deploy phase and record evidence.
- **Phase keywords:** Ignore `Workspace: <path>` when matching phase cues so temp paths under `pytest-*` do not false-trigger `pytest` / test phases.

---

## Acceptance checklist (this pass)

- [x] Proactive intro + `PULSE.md` on operator turns (`NEXA_OPERATOR_PROACTIVE_INTRO`).
- [x] Step-by-step **Live progress** block before evidence sections.
- [x] PULSE re-read each turn; inject capped content (~12k chars).
- [x] Strict `verified` + mission footer only when proof bar is met.
- [x] No fake “mission complete” on verify failure (e.g. HTTP 502).
- [x] PULSE can skip deploy when forbidden phrases appear.
- [x] Tests in `tests/test_operator_enhanced_orchestration_slice.py` (+ operator suite).

---

## Implementation map

| Area | Module |
|------|--------|
| Live steps + strict verification + mission footer | `app/services/operator_execution_loop.py` |
| PULSE read / deploy-skip heuristic | `app/services/operator_pulse.py` |
| Success-language guard | `app/services/operator_runners/base.py` (`forbid_unverified_success_language`) |
| Gateway intro wrapper (unchanged) | `app/services/gateway/runtime.py` |

---

*End of Phase 2 spec.*
