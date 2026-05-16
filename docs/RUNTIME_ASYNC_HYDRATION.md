# Runtime async hydration (Phase 4 Step 7)

Progressive truth assembly uses priority tiers: `critical` → `operational` → `advisory` → `background`.

- `hydrate_progressive_truth()` in `runtime_async_hydration.py`
- `GET /api/v1/runtime/hydration` — queue and status
- `GET /api/v1/runtime/profile/{profile}` — profile-specific partial truth

Mission Control Office uses progressive hydration before full evolution layers complete.
