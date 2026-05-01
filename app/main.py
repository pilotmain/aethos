from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.routes import (
    agent_organization,
    agent_runtime_api,
    apple_messages,
    audit_export,
    auth,
    channels,
    checkins,
    custom_agents_api,
    dashboard,
    dumps,
    email,
    governance_api,
    health,
    internal,
    jobs,
    memory,
    mission_control,
    permissions,
    report_watcher,
    plans,
    slack,
    sms,
    tasks,
    trust,
    web,
    whatsapp,
)
from app.core.config import get_settings, print_llm_debug_banner, print_local_service_urls
from app.services.startup_config_log import log_sanitized_nexa_config, maybe_log_llm_key_hint
from app.core.db import ensure_schema
from app.core.scheduler import scheduler
from app.models import *  # noqa: F401,F403
from app.workers.followup_worker import process_due_checkins
from app.workers.operator_supervisor import process_supervisor_cycle

settings = get_settings()
ensure_schema()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.startup_ensure import (
        ensure_nexa_secret_key,
        print_env_validation_at_startup,
        print_missing_python_modules_hint,
    )

    ensure_nexa_secret_key()
    get_settings.cache_clear()
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
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
_cors = [o.strip() for o in (settings.nexa_web_origins or "").split(",") if o.strip()]
if not _cors:
    # Empty env must not disable CORS — browser would get opaque "Failed to fetch" on every API call.
    _cors = ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(dashboard.router)
app.include_router(health.router, prefix=settings.api_v1_prefix)
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
app.include_router(jobs.router, prefix=settings.api_v1_prefix)
app.include_router(web.router, prefix=settings.api_v1_prefix)
app.include_router(permissions.router, prefix=settings.api_v1_prefix)
app.include_router(trust.router, prefix=settings.api_v1_prefix)
app.include_router(mission_control.router, prefix=settings.api_v1_prefix)
app.include_router(agent_runtime_api.router, prefix=settings.api_v1_prefix)
app.include_router(report_watcher.router, prefix=settings.api_v1_prefix)
app.include_router(agent_organization.router, prefix=settings.api_v1_prefix)
app.include_router(slack.router, prefix=settings.api_v1_prefix)
app.include_router(email.router, prefix=settings.api_v1_prefix)
app.include_router(whatsapp.router, prefix=settings.api_v1_prefix)
app.include_router(sms.router, prefix=settings.api_v1_prefix)
app.include_router(apple_messages.router, prefix=settings.api_v1_prefix)
app.include_router(internal.router, prefix=settings.api_v1_prefix)
