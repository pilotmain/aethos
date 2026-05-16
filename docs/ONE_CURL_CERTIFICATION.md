# One-curl certification (Phase 4 Step 11)

Certified flow:

```text
curl | bash → install.sh → scripts/setup.sh → scripts/setup.py
  → enterprise setup extensions → Mission Control seed → health checks
```

**Verify:** `aethos setup certify` or `GET /api/v1/setup/one-curl`

Module: `app/services/setup/setup_path_certification.py`
