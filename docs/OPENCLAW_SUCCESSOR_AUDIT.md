# OpenClaw successor roadmap — Nexa-next coverage audit (Phase 54)

This document compares strategic themes against the **current** `nexa-next` codebase. Status values: **implemented**, **partial**, **missing**, **deferred**.

## Summary table

| Feature | OpenClaw strength | Nexa current state | Status | Next action |
| --- | --- | --- | --- | --- |
| Privacy firewall / PII handling | Good UX | Gateway + redaction + modes | implemented | Keep tightening detectors |
| Token / cost transparency | Variable | Token economy + MC panels | implemented | Expand per-mission rollups |
| Local-first routing | Strong story | Ollama + `NEXA_LOCAL_FIRST` | partial | More local runtimes in catalog |
| Execution governance | Skills run wild | Approvals + workspace gates | partial | Finish sandbox runners beyond process |
| Zero-trust sandbox | MicroVM hype | Policy enums + docker probe MVP | partial | Wire Docker runner for skills |
| Credential vault | OS keychain | In-memory placeholder + API | partial | Add keychain backend |
| Permission consents | OS-like | In-memory consent store MVP | partial | Persist + UI prompts |
| Audit ledger | Marketing | Hash-chained in-memory ledger MVP | partial | Persist + tamper alerts |
| Network egress control | Rare | Host allowlist + gateway hook | partial | Enforce on every HTTP path |
| One-line install | Strong | `install.sh` + bootstrap + doctor | partial | Harden CI matrix |
| Voice UX | Strong | Flagged stub + policy | partial | Local ASR integration |
| Multimodal | Strong | Privacy-gated stub | partial | Vision router to local model |
| Workflow engine | YAML hype | Topo sort YAML MVP | partial | Real step executors |
| Skills marketplace | Large catalog | Local JSON + validation MVP | partial | Signing + review UI |
| Mission Control | Dashboard | Live state + safety panel | partial | Operator-first copy everywhere |
| Enterprise SSO / fleet | Roadmap | Governance hooks exist | deferred | Not in Phase 54 scope |
| Marketing honesty | Mixed | Claim guard tests + public docs | partial | Keep docs synced with code |

## 1. Privacy & Security

| Feature | OpenClaw strength | Nexa current state | Status | Next action |
| --- | --- | --- | --- | --- |
| PII redaction | Basic | Privacy firewall + scanners | implemented | — |
| Strict / paranoid modes | Binary | `nexa_strict_privacy_mode` + user mode | implemented | — |
| Sandboxed execution | Implied | `SandboxMode` + policy resolution | partial | Real container isolation |
| Secrets management | Ad hoc | Vault interface (local placeholder) | partial | OS keychain provider |
| Audit trail | Logs | Hash-chained ledger MVP | partial | Durable storage |
| Egress allowlisting | Rare | `network_policy` + provider gateway | partial | Extend to all httpx call sites |

## 2. Installation & Onboarding

| Feature | OpenClaw strength | Nexa current state | Status | Next action |
| --- | --- | --- | --- | --- |
| Single script install | Yes | `scripts/install.sh` + `nexa_bootstrap.py` | partial | More CI smoke jobs |
| Env defaults | Mixed | Bootstrap writes privacy-first lines | implemented | Verify Docker template parity |
| Doctor command | Some | `scripts/nexa_doctor.sh` | partial | Narrow compose service names |

## 3. Reliability & Autonomy

| Feature | OpenClaw strength | Nexa current state | Status | Next action |
| --- | --- | --- | --- | --- |
| Heartbeat / scheduler | Yes | APScheduler + autonomy loop | implemented | — |
| Deterministic workflows | Implied | YAML workflow engine MVP | partial | Dev step bindings |
| Run steering | Chat commands | Dev run cancel/pause/resume API layer | partial | Wire executor to honor pause |
| Memory provenance | Weak | JSON helpers on memory blobs | partial | DB columns when schema migrates |

## 4. Performance / Cost / Hardware

| Feature | OpenClaw strength | Nexa current state | Status | Next action |
| --- | --- | --- | --- | --- |
| Cost caps | Opaque | Token budgets + blocking | implemented | — |
| Local GPU paths | Story | Catalog doc + Ollama flags | partial | Auto-detect runtimes |
| Resource limits | None | Config-only policy struct | partial | Enforce cgroups later |

## 5. Advanced Capabilities

| Feature | OpenClaw strength | Nexa current state | Status | Next action |
| --- | --- | --- | --- | --- |
| Voice | First-class | Stub + strict privacy gate | partial | Local Whisper |
| Multimodal | Strong | Router stub | partial | Local vision model |
| Browser / tools | Wide | Allowlisted fetch + browser flags | partial | Expand cautiously |

## 6. Developer Experience / Ecosystem

| Feature | OpenClaw strength | Nexa current state | Status | Next action |
| --- | --- | --- | --- | --- |
| Skills | Large | User JSON + packaged manifests + marketplace file | partial | Executor + signing |
| SDK | Multiple langs | Python TypedDict types under `app/services/sdk` | partial | Publish package |
| Docs | Viral | Honest comparison docs (this phase) | implemented | Update each release |

## 7. Marketing / Adoption

| Feature | OpenClaw strength | Nexa current state | Status | Next action |
| --- | --- | --- | --- | --- |
| Migration guides | Few | `MIGRATING_FROM_OPENCLAW.md` | partial | Community feedback |
| Positioning | Hype-heavy | `WHY_NEXA.md` (balanced) | partial | Case studies |

## 8. Monetization / Sustainability

| Feature | OpenClaw strength | Nexa current state | Status | Next action |
| --- | --- | --- | --- | --- |
| Hosted billing | Unknown | Not productized in repo | missing | Deferred |
| Enterprise contracts | Unknown | No SOC2 claims in runtime | deferred | Legal/commercial track |

---

_Update this file when features move from partial → implemented._
