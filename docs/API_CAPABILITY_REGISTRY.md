# API capability registry

`GET /api/v1/runtime/capabilities` lists available Mission Control routes, feature flags, and `mc_compatibility_version` (`phase4_step6`).

Frontend and CLI should probe capabilities before calling optional endpoints.
