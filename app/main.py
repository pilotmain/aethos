from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.routes import (
    admin_privacy,
    agent_organization,
    agent_runtime_api,
    apple_messages,
    audit_export,
    auth,
    channels,
    checkins,
    custom_agents_api,
    dashboard,
    dev_runtime,
    dumps,
    email,
    governance_api,
    health,
    internal,
    jobs,
    memory,
    mission_control,
    nexa_memory_layer,
    nexa_scheduler_api,
    nexa_skills_api,
    permissions,
    plans,
    report_watcher,
    slack,
    sms,
    system,
    tasks,
    trust,
    user_settings,
    web,
    whatsapp,
)
from app.core.config import get_settings, print_llm_debug_banner, print_local_service_urls
from app.core.db import ensure_schema
from app.core.scheduler import scheduler
from app.middleware.metrics import MetricsMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.models import *  # noqa: F401,F403
from app.services.logging.logger import configure_logging
from app.services.startup_config_log import log_sanitized_nexa_config, maybe_log_llm_key_hint
from app.workers.followup_worker import process_due_checkins
from app.workers.operator_supervisor import process_supervisor_cycle

settings = get_settings()
ensure_schema()


def _retention_sweep() -> None:
    from app.core.db import SessionLocal
    from app.services.cleanup.retention import run_retention_cleanup

    log = logging.getLogger("nexa")
    with SessionLocal() as db:
        try:
            out = run_retention_cleanup(db)
            if out.get("missions_deleted") or out.get("external_calls_deleted"):
                log.info("retention.cleanup %s", out)
        except Exception as exc:
            log.warning("retention sweep failed: %s", exc)


def _http_error_detail(exc: StarletteHTTPException) -> str:
    d = exc.detail
    if isinstance(d, str):
        return d
    try:
        return json.dumps(d)
    except Exception:
        return str(d)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings.cache_clear()
    _boot = get_settings()
    configure_logging(logging.WARNING if _boot.nexa_production_mode else logging.INFO)
    app.debug = not _boot.nexa_production_mode and bool(_boot.debug)
    from app.services.startup_ensure import (
        ensure_nexa_secret_key,
        print_env_validation_at_startup,
        print_missing_python_modules_hint,
    )

    ensure_nexa_secret_key()
    from app.services.plugins.registry import load_plugins

    load_plugins()
    s = get_settings()
    log_sanitized_nexa_config("api")
    print_env_validation_at_startup("api")
    print_missing_python_modules_hint()
    print_llm_debug_banner()
    maybe_log_llm_key_hint()
    print_local_service_urls()
    if not scheduler.running:
        scheduler.add_job(
            process_due_checkins,
            "interval",
            seconds=s.followup_poll_seconds,
            id="due_checkins",
            replace_existing=True,
        )
        scheduler.add_job(
            process_supervisor_cycle,
            "interval",
            seconds=s.operator_poll_seconds,
            id="operator_supervisor",
            replace_existing=True,
        )
        if s.nexa_retention_sweep_interval_seconds > 0:
            scheduler.add_job(
                _retention_sweep,
                "interval",
                seconds=s.nexa_retention_sweep_interval_seconds,
                id="nexa_retention",
                replace_existing=True,
            )
        scheduler.start()
    try:
        from app.core.db import SessionLocal
        from app.services.scheduler.service import register_apscheduler_jobs_from_db

        with SessionLocal() as db:
            n = register_apscheduler_jobs_from_db(db)
            logging.getLogger("nexa").info("nexa.scheduler.restored count=%s", n)
    except Exception as exc:
        logging.getLogger("nexa").warning("nexa.scheduler.restore_failed %s", exc)
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
# Browser Origin must be listed or fetch fails with an opaque network error (looks like "wrong URL").
# scripts/nexa_next_local_all.sh serves Next on :3120; merge these even when .env only lists :3000.
_extra_local_web_origins = ("http://localhost:3120", "http://127.0.0.1:3120")
_cors = [o.strip() for o in (settings.nexa_web_origins or "").split(",") if o.strip()]
if not _cors:
    # Empty env must not disable CORS — browser would get opaque "Failed to fetch" on every API call.
    _cors = ["http://localhost:3000", "http://127.0.0.1:3000", *_extra_local_web_origins]
else:
    _cors = list(dict.fromkeys([*_cors, *_extra_local_web_origins]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(MetricsMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(dashboard.router)
app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(system.router, prefix=settings.api_v1_prefix)
app.include_router(admin_privacy.router, prefix=settings.api_v1_prefix)
app.include_router(channels.router, prefix=settings.api_v1_prefix)
app.include_router(governance_api.router, prefix=settings.api_v1_prefix)
app.include_router(custom_agents_api.router, prefix=settings.api_v1_prefix)
app.include_router(audit_export.router, prefix=settings.api_v1_prefix)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(tasks.router, prefix=settings.api_v1_prefix)
app.include_router(dumps.router, prefix=settings.api_v1_prefix)
app.include_router(plans.router, prefix=settings.api_v1_prefix)
app.include_router(checkins.router, prefix=settings.api_v1_prefix)
app.include_router(memory.router, prefix=settings.api_v1_prefix)
app.include_router(nexa_memory_layer.router, prefix=settings.api_v1_prefix)
app.include_router(nexa_scheduler_api.router, prefix=settings.api_v1_prefix)
app.include_router(nexa_skills_api.router, prefix=settings.api_v1_prefix)
app.include_router(jobs.router, prefix=settings.api_v1_prefix)
app.include_router(web.router, prefix=settings.api_v1_prefix)
app.include_router(permissions.router, prefix=settings.api_v1_prefix)
app.include_router(trust.router, prefix=settings.api_v1_prefix)
app.include_router(user_settings.router, prefix=settings.api_v1_prefix)
app.include_router(mission_control.router, prefix=settings.api_v1_prefix)
app.include_router(dev_runtime.router, prefix=settings.api_v1_prefix)
app.include_router(agent_runtime_api.router, prefix=settings.api_v1_prefix)
app.include_router(report_watcher.router, prefix=settings.api_v1_prefix)
app.include_router(agent_organization.router, prefix=settings.api_v1_prefix)
app.include_router(slack.router, prefix=settings.api_v1_prefix)
app.include_router(email.router, prefix=settings.api_v1_prefix)
app.include_router(whatsapp.router, prefix=settings.api_v1_prefix)
app.include_router(sms.router, prefix=settings.api_v1_prefix)
app.include_router(apple_messages.router, prefix=settings.api_v1_prefix)
app.include_router(internal.router, prefix=settings.api_v1_prefix)


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errs = exc.errors()
    msg = "Validation error"
    if errs:
        e0 = errs[0]
        loc = ".".join(str(x) for x in e0.get("loc", ()) if x != "body")
        msg = f"{loc}: {e0.get('msg', 'invalid')}" if loc else str(e0.get("msg", msg))
    return JSONResponse(
        status_code=422,
        content={"ok": False, "error": msg, "code": "VALIDATION_ERROR"},
    )


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = f"HTTP_{exc.status_code}"
    if exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 401:
        code = "UNAUTHORIZED"
    elif exc.status_code == 403:
        code = "FORBIDDEN"
    elif exc.status_code == 410:
        code = "GONE"

    d: Any = exc.detail
    msg = _http_error_detail(exc)
    body: dict[str, Any] = {"ok": False, "code": code}
    if isinstance(d, dict):
        body["detail"] = d
        body["error"] = str(d.get("error") or msg)
    elif isinstance(d, str):
        body["detail"] = d
        body["error"] = d
    elif isinstance(d, list):
        body["detail"] = d
        body["error"] = msg
    else:
        body["detail"] = d if d is not None else msg
        body["error"] = msg

    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("nexa").exception("unhandled error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": "Internal server error", "code": "INTERNAL_ERROR"},
    )
