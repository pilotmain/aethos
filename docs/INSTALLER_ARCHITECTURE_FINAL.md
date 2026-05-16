# Installer architecture (final)

```text
install.sh → scripts/setup.sh → aethos setup
                ↓
    setup_wizard + orchestrator_onboarding + setup_mission_control
                ↓
    app/services/setup/* APIs
                ↓
    Mission Control (seeded connection)
```

Cohesive by design — not legacy shell plus patches.
