# Runtime ownership model

One active **runtime owner** per machine (`~/.aethos/runtime/ownership.lock`). Uvicorn reload parents do not acquire ownership; API workers do.

- **Observer mode:** API running without lock when another owner is live
- **Takeover:** `aethos runtime takeover --yes`
- **Release:** `aethos runtime release`
