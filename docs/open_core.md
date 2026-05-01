# Nexa Open Core Strategy

Nexa provides an **open, inspectable safety layer** for AI agents, with a **proprietary product layer** for production use.

This document describes how Nexa separates **inspectable safety** (open) from **product and control** (proprietary). It aligns with the `LICENSE` (Apache-2.0) in this repository when that license applies to the published tree.

## What this repo proves

This repository demonstrates that:

- **Privileged actions** can be **structurally enforced** (not merely instructed via prompts)
- **Permissions** can be explicit, scoped, and **auditable**
- **Outbound data** (**egress**) can be **controlled** at execution boundaries
- **Behavior** can be **inspected and verified** against **safety policy** and audit records

Together, these properties answer “why trust Nexa?” at the architectural level — without requiring readers to parse implementation details.

## Principle

**Open the trust substrate. Monetize the control and experience layer.**

## Open vs closed (explicit)

**Open (trust layer — intended for public core):**

- Versioned **safety policy** and downgrade protection
- **Enforcement pipeline** (policy guard, ordering, host execution + **egress** gates)
- **Permission** model (scopes, grants, consumption, audit hooks)
- **Provenance** (`instruction_source`, trust boundaries — non-spoofable from untrusted payloads)
- **Audit** primitives (events emitted at execution boundaries)

**Closed (product layer — proprietary):**

- Workflow orchestration and agent product logic above the core
- **UI** (dashboard, trust / activity timeline, builders)
- Third-party **integrations** (Slack, Jira, enterprise IdP, …)
- **Hosted** runtime, multi-tenant isolation, billing / SaaS

Keeping this split obvious avoids “what are we actually getting in OSS?” confusion before v1.

## Not included (open-core boundary)

What this strategy treats as **outside** the public trust slice (unless explicitly published elsewhere):

- Workflow orchestration above the core
- End-user **UI** and dashboards
- Third-party **integrations**
- **Hosted** runtime and SaaS operations

If it is not needed to **verify** safety claims in code, it does not belong in the minimal open release.

## Trust guarantee (structural)

For paths wired through Nexa’s enforcement layer, **privileged actions** are not “prompt-only”: they are expected to pass, in order, **safety policy verification**, **provenance checks**, **permission checks** where the product enforces grants, and **egress controls** when data leaves the **local environment**. **Audit** records are emitted so behavior can be reconstructed and reviewed. Exact flags and surfaces depend on deployment; the architecture is built so safety is enforceable in code, not inferred from chat history.

## Structural flow (reference)

```
User action
       ↓
Safety policy verification
       ↓
Provenance / instruction trust
       ↓
Permission check
       ↓
Execution (host / tools)
       ↓
Egress gate (when applicable)
       ↓
Audit event
```

**Egress** means controls that apply when data **leaves the local environment**. In prose we also call this **outbound** or **external send** traffic — for example **external network requests** or other off-machine sends that the product chooses to gate.

## Replication (realistic)

Copying cannot be prevented. Nexa increases **cost to replicate as a product** through integrations, onboarding, observability and trust UX, enterprise controls, hosted operation, support, and iteration speed. The **core safety machinery** remaining forkable is intentional for trust.

## Licensing (default recommendation)

- **nexa-core (public):** Apache-2.0 — broad adoption, explicit patent grant, enterprise-friendly.
- **nexa-pro / nexa-cloud (private):** Proprietary.

**Avoid:** mixing OSS and proprietary code in the **same** repository, or applying source-available licenses to the core trust layer without a strong reason — that undermines adoption and the “inspectable safety” narrative.

## Repository rules

1. **One repo = one license.** No mixed-license trees.
2. **Dependency direction:** `nexa-core` → `nexa-pro` → `nexa-cloud`. **Core must never depend on pro or cloud.**
3. **Interfaces in core:** Core defines what counts as **privileged actions**, permission checks, audit emission, and **egress** (external-send) gating. Pro/Cloud implement plugins, UX, and hosted services.
4. **CI:** Fail builds if core imports private modules; optional grep/import-linter rules to prevent leaks.
5. **Bridge pattern (optional):** Core loads Pro extensions when installed as an extra, without hard-coupling the OSS tree to private code.

## v1 public slice (minimal)

When publishing **nexa-core** v1, scope stays intentionally small:

- Safety policy (versioned, non-compactable semantics in code)
- Policy guard / enforcement ordering
- Provenance (`instruction_source`, trust boundaries)
- Permission model (scopes, grants, audit hooks)
- Outbound and host execution gates
- Tests covering policy and enforcement (e.g. P0 / P0.5-style coverage)
- One short verification doc (how to run tests and interpret the pipeline)

Everything else stays private until a deliberate second slice.

## Narrative (one flow)

Single story for README and launch:

**user action → safety policy → permission → execution → egress → audit**

Positioning line (consistent use):

**Inspectable agent safety** — *open execution safety you can verify; product and cloud layers for teams who run it in production.*

## Contributor / security hygiene (when public)

Add when ready: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`; keep `SECURITY.md` updated (see repo root).

## Related

- [SECURITY.md](../SECURITY.md) — vulnerability reporting  
- Making trust **legible** to end users is a **product** concern; the open core is what makes safety claims **checkable** in code and tests.

---

**Takeaway:** Nexa’s **open core** lets anyone verify **how safety is enforced**; the **product layer** focuses on making that safety **usable** in real workflows.

---

*Do not expand the v1 open slice until the first release proves: safety is enforced structurally and can be verified by reading code and tests.*

*This document stays small and architectural: trust and boundaries — not implementation.*
