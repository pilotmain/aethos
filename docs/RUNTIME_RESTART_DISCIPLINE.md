# Runtime restart discipline (Phase 4 Step 10)

**CLI:**

```bash
aethos restart api|web|bot|runtime|connection|all
```

`runtime_restart_manager.py` records bounded restart history.

**API:** `GET /api/v1/runtime/restarts`
