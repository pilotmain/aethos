# Compatibility alias policy

Backward-compatible env names remain for operators migrating from Nexa-named tooling.

| Preferred | Alias |
|-----------|--------|
| `AETHOS_API_URL` | `NEXA_API_BASE` |
| `AETHOS_API_BEARER` | `NEXA_WEB_API_TOKEN` |
| `AETHOS_USER_ID` | `TEST_X_USER_ID` / `X_USER_ID` |

New deployments should use **AETHOS_*** names. Aliases are not shown in Mission Control UI.
