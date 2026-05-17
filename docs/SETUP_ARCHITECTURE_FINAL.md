# Setup architecture (final)

| Layer | Role |
|-------|------|
| `install.sh` | Public entry — clone/update, delegate |
| `scripts/setup.sh` | Venv bootstrap, `pip install`, invoke `aethos setup` |
| `aethos setup` | Enterprise conversational wizard (`setup_wizard.py`) |
| `setup_enterprise.py` | Routing, channels, onboarding profile |
| `setup_mission_control.py` | Bearer token, web `.env.local`, connection profile |

`scripts/setup.py` is a **compatibility shim** (delegates to `aethos setup`). Legacy numbered wizard: `AETHOS_SETUP_LEGACY=1 python scripts/setup.py`.
