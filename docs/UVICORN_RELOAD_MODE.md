# Uvicorn reload mode

With `--reload`, the parent reloader does not acquire runtime ownership. The worker sets `AETHOS_UVICORN_WORKER=1` in lifespan. Service registry filters reloader parents to avoid false duplicate API warnings.
