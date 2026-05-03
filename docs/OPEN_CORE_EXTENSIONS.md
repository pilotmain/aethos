# Open core extension hooks

The codebase follows an **open core** model: everything in this repository runs without proprietary wheels. Optional commercial packages can extend behavior via Python imports.

## `nexa_ext.*` modules

`app.services.extensions.get_extension("sandbox")` tries `import nexa_ext.sandbox`. If the module is missing, callers **must** fall back (see `app/services/sandbox/runner.py`).

Commercial distributions may ship:

- a pip package exposing the `nexa_ext` namespace, or  
- a Docker layer / mounted tree on `PYTHONPATH`.

Core code **never** imports proprietary modules directly—only through `get_extension`.

## License verification

`app.services/licensing.has_pro_feature(feature_id)` returns true only when:

- `NEXA_LICENSE_KEY` is set to a **signed** token (`nexa_lic_v1.<payload>.<sig>`), and  
- `NEXA_LICENSE_PUBLIC_KEY_PEM` contains the matching **Ed25519 public key** (PEM).

Without a verified key in settings, commercial feature flags remain **off** (OSS default).

Token payload is JSON, for example:

```json
{"features": ["sandbox_advanced"], "exp": 1893456000}
```

Signing is Ed25519 over the **raw UTF-8 bytes** of that JSON (the middle segment of the token).

## Repository license

This tree is released under **Apache-2.0** — see `LICENSE`. Closed-source layers ship separately under commercial terms.
