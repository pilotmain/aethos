# Public roadmap (aspiration-friendly)

Items below mix **shipped foundations** with **aspiration**. Unless a bullet explicitly says *landed in Phase 54*, treat dates as non-promissory.

## Near term (engineering focus)

- **Sandbox**: Expand `docker` execution paths for skills; keep `gvisor` / `firecracker` opt-in only when runtime integration exists.
- **Vault**: Replace local placeholder with OS keychain providers where available.
- **Egress**: Extend policy checks to every outbound HTTP helper—not only the provider gateway.
- **Voice**: Local transcription defaults; optional external ASR only after explicit consent.

## Medium term (aspiration)

- Signed skill packages with review queues before activation.
- Persistent audit ledger + export for compliance workflows.
- Deeper Mission Control “operator console” language (less dashboard chrome).

## Explicit non-goals (for now)

- Claiming SOC 2 / enterprise certification without external audit artifacts.
- Promising full replacement of human teams or unsupervised autonomy in regulated environments.

---

### Marketing guardrails

Words implying guarantees, formal auditor sign-off, or total replacement of another product should only appear in **aspiration** sections like this document—not in runtime copy or unchecked README bullets.
