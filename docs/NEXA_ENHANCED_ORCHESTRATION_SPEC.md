# NEXA_ENHANCED_ORCHESTRATION_SPEC.md

**Title:** Nexa Enhanced Orchestration Specification – Borrow OpenClaw Magic + Make It Better  
**Version:** 1.0 (Target for immediate implementation on top of current handoff)  
**Status:** Complete Engineering + Product Target Spec  
**Goal:** Minimum = Nexa feels and works exactly like OpenClaw’s magical orchestration (Heartbeat + Lobster-style deterministic workflows + persistent Markdown memory + proactive gateway).  
**Maximum** = Nexa is clearly superior: privacy-first zero-trust, verifiable truth layer, lighter tokens, Mission Control observability, safer operator mode, end-to-end autonomous operator behavior without repeated confirmations.

This spec builds directly on your existing handoff (`execution_loop.py`, `operator_execution_loop.py`, gateway runtime, etc.) and injects OpenClaw’s proven “magic feel” while fixing its weaknesses.

---

## 1. Core User Promise (The Magic Feel)

**End-to-end orchestration** in Nexa means: User gives a high-level intent (“fix the Railway worker crash and redeploy”, “ship latest main to Vercel production”, “add auth and push the feature branch”) and Nexa autonomously executes the full lifecycle while feeling alive and proactive.

When the user asks for work:

- Nexa immediately replies: “Understood. Entering Operator Mode for [clear mission summary]. I will inspect → diagnose → fix → test → commit → push → deploy → verify. Live progress in Mission Control. Only true blockers will stop me.”
- It switches to **full Operator Mode** (no repeated confirmations for every command).
- It uses OpenClaw-style **Heartbeat/Pulse** for background continuity and **Lobster-style deterministic pipelines** for multi-step safety and efficiency.
- Difference from other modes:
  - **Chat/Guidance**: Only suggests.
  - **Diagnostic-only**: Inspect + report, no writes.
  - **Real Execution (Operator Mode)**: Full autonomous loop with proof at every verified step.

---

## 2. Operator Mode (Borrowed + Improved from OpenClaw)

**Activation:** Same as your handoff + natural phrases (“operator mode on”, “fix and ship it”, “run end-to-end”).

**Capabilities (exactly like OpenClaw + better):**

- Given a workspace path (auto-detected or user-provided).
- Full local repo inspection (`git status`, `git log`, file reads) — OpenClaw style.
- Run any terminal/CLI command via sandboxed runner.
- Modify files via secure diff/patch (never blind `echo`).
- Run tests/builds (`npm test`, etc.).
- Commit & push with semantic messages.
- Deploy/redeploy (Vercel, Railway, etc.).
- Watch logs + health checks + automatic retry.
- Continues until true blocker or success.

**Nexa improvements over OpenClaw:**

- Zero-trust micro-VM per command (Firecracker/gVisor).
- Credential vault (OS keychain, never plaintext).
- Mission Control shows every command + output + verified state.
- No repeated approvals in Operator Mode (your handoff goal achieved safely).

---

## 3. Credential/Login Flow (Improved from Your Handoff)

Exactly as in your handoff, plus:

- If user pastes token in chat → Nexa stores in OS vault, tests immediately (`vercel whoami`, `railway whoami`, `gh auth status`), confirms without echoing secret.
- Auto-detects existing CLI logins.
- Guides `vercel login`, `railway login`, `gh auth login` via browser/terminal where possible.
- Verifies every credential before any write/deploy action.
- Never stores or echoes secrets in logs/chat.

---

## 4. Execution Loop (The Core Magic – OpenClaw + Nexa)

**Nexa combines your execution_loop + operator_execution_loop with OpenClaw’s proven pattern:**

1. **Detect intent** → clear mission + success criteria.
2. **Safe checks first** (git status, current branch, tests) — OpenClaw style.
3. **Heartbeat/Pulse integration**: Background pulse continues the mission even if chat closes (reads `PULSE.md` or `HEARTBEAT.md` equivalent).
4. **Deterministic pipeline (NexaForge = Lobster 2.0)**: Multi-step via typed JSON-pipe DAG with hard approval gates only on true side-effects.
5. **Progress loop**:
   - Inspect → Diagnose (with proof) → Fix (patch) → Test → Commit/Push → Deploy → Watch logs → Verify (health check).
   - Automatic smart retries (transient failures, backoff).
   - Stops only on true blocker with exact evidence.
6. **No “paste logs”** — Nexa fetches and analyzes itself.

**User-visible in chat (magic feel):**

- Short confident updates every 15–45s.
- Final summary with proof links.

---

## 5. Progress and “Magic Feel”

**Chat:**

- Proactive, concise, alive tone (“Inspecting repo… Found root cause in worker.js… Applying fix… Pushing… Deploying to Vercel… Verified healthy after 42s.”).

**Mission Control (required UI):**

- Live timeline, current step, last command + output, logs/results, blockers with proof, verified state (green only with proof), retry/resume buttons.
- Never fake “Completed” — only “Verified” after real checks.

**Heartbeat/Pulse (OpenClaw magic borrowed):**

- Periodic background turns that continue Operator missions.
- Reads `PULSE.md` for standing orders.
- Feels like the agent is always working for you.

---

## 6. Truth and Verification (Nexa’s Biggest Upgrade)

Nexa never lies:

- “Fixed” / “Deployed” / “Healthy” only after real proof (command success + follow-up check).
- Exact blocker messages with logs/SHA/URL.
- All states in Mission Control are backed by evidence.

---

## 7. Provider-Specific Runners (Built on Your Handoff)

- Vercel, Railway, GitHub, Generic shell — exactly as in your operator_runners.
- Read-only always allowed.
- Write/deploy gated by flags + credential verification.
- Retry loops built-in for transient issues.

---

## 8. Safety Model (Operator Mode as Requested)

- Operator Mode = autonomous (no repeated approvals per command).
- Still protects: destructive ambiguity aborts, secret scanning, PII egress block, sandbox per action.
- Config flags: `NEXA_OPERATOR_MODE`, `NEXA_OPERATOR_ALLOW_WRITE`, `NEXA_OPERATOR_ALLOW_DEPLOY`, etc. (your handoff).

---

## 9. Memory and Context

- Persistent Markdown files (`SOUL.md`, `PULSE.md`, project memory) — exactly OpenClaw style but with vector search + provenance.
- Loads only relevant context (previous failures, last SHA).
- Lightweight, no GPU required, token-efficient via deterministic NexaForge steps.

---

## 10. Mission Control Requirements

Live view must show:

- Active mission + criteria.
- Current step + elapsed time.
- Last command + output.
- Real logs/results.
- Blockers with proof.
- Verified state (proof-backed).
- Retry/resume.
- No fake green states.

---

## 11. Test Cases (Build These)

Include tests for:

- Vercel deploy failure auto-repair + verify.
- Railway worker crash fix + redeploy.
- Full GitHub push → Vercel deploy flow.
- Token pasted in chat → secure store + verify.
- Existing CLI login detection.
- Missing CLI → install + login guidance.
- Background Pulse continuation after chat close.
- Transient retry success.
- No repeated confirmations in Operator Mode.
- No fake success (502 → exact blocker report).
- Mission Control truthful display.

---

## 12. Acceptance Criteria

Nexa is “OpenClaw-level magic + better” when:

- User gives one sentence → full autonomous operator loop completes with zero repeated confirmations (Operator Mode).
- Every success claim is proof-backed.
- Heartbeat/Pulse + NexaForge give the exact same “alive” proactive feel as OpenClaw.
- Credential flow and safety match or exceed your current handoff.
- All test cases pass.
- Token usage is lower than OpenClaw equivalents (deterministic pipelines).
- Mission Control shows truthful, observable state.

**This spec makes Nexa work exactly like OpenClaw’s magical orchestration at minimum, and clearly better at maximum.**

---

## 13. Implementation status (this repository)

**Shipped in a bounded slice (code + tests):**

- **Phase 2 (OpenClaw-style chat):** `### Live progress` step lines, strict deploy+verify proof for `verified` / mission footer, PULSE-driven deploy skip, workspace-stripped phase keyword detection (see `docs/NEXA_ENHANCED_ORCHESTRATION_PHASE2.md`).
- **Proactive gateway copy** when `NEXA_OPERATOR_MODE` is on: first line of operator / execution-loop replies can include a short “Understood / operator-style run” preamble before deterministic output. Toggle with **`NEXA_OPERATOR_PROACTIVE_INTRO`** (default `true`). Implemented in `app/services/operator_orchestration_intro.py` and `gateway_finalize_operator_or_execution_reply` in `app/services/gateway/runtime.py`.
- **Read-only `PULSE.md` surfacing**: when a workspace root is known for the operator turn, non-empty `PULSE.md` / `pulse.md` text (size-capped) is appended under “Standing orders (PULSE.md)”. Implemented in `app/services/operator_pulse.py` and wired from `try_operator_execution`. This does **not** execute instructions in the file or continue work after the HTTP request ends.

**Still product / infra work (not implied by the slice above):**

- Per-command Firecracker/gVisor isolation, OS keychain vault, full Mission Control live UI, NexaForge JSON DAG engine, vector memory + `SOUL.md` productization, true background continuation of the same mission after the chat session closes, and the full §11 integration test matrix beyond existing operator/execution tests.

See `docs/HANDOFF_OPERATOR_EXECUTION_AND_ORCHESTRATION.md` for the baseline handoff architecture.

*End of spec.*
