# Response suggestion audit (Phase 51)

Decision table for paths that historically produced “suggest instead of execute” or legacy identity copy.

| Location | Previous behavior | Phase 51 behavior | Status |
|----------|-------------------|-------------------|--------|
| `dev_runtime/gateway_hint.py` | REST registration hints | No workspace: natural language; multiple: pick workspace; single: `run_dev_mission` | Rewritten |
| `dev_runtime/run_dev_gateway.py` | REST for empty goal / multi workspace | Mission Control + bullet workspace list | Rewritten |
| `gateway/runtime.py` `gateway_finalize_chat_reply` | Log only | Scrub when legacy / REST patterns detected | Active scrub |
| `identity/scrub.py` | — | Central replacements for REST / “tell Cursor” / labels | Added |
| `web_chat_service.py` main path | `handle_agent_request` only | `NexaGateway.handle_message` first; fallback to orchestrator | Gateway-first |
| `agent_orchestrator.py` developer route | “tell Cursor” phrasing | Action-oriented Nexa copy | Rewritten |
| `telegram_onboarding.py` | Slash-first, `@reset`, `/agents` | Intent-first examples; minimal `/help` | Rewritten |
| `command_help.py` | Already intent-first | Unchanged | Keep |
| `response_sanitizer.py` | `_DEV_DISABLED` / execution-lead mentioned Cursor | Nexa-neutral wording (host executor / IDE-linked) | Rewritten |
| `local_file_intent.py` | “in EKS” / stack words → bogus paths; URLs → path UX | Tech-keyword denylist, URL deferral, infra-without-path → no host match | Rewritten |
| `input_secret_guard.py` | — | Block pasted API keys before host/path routing | Added |
| `instant_dev_assist.format_assist_appendix` | Context appendix | Still appends in gateway full chat via `_merge_phase50_assist` | Keep |

Review periodically when adding new outbound strings.
