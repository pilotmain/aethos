# Enterprise runtime coordination (Phase 4 Step 25)

Process groups are managed via `app/services/runtime/runtime_process_group_manager.py`. Restart and recovery use full process-group termination (uvicorn parent/worker, Telegram, hydration orphans).

CLI: `aethos runtime stop`, `aethos runtime restart`, `aethos runtime restart --clean`, `aethos runtime recover`.
