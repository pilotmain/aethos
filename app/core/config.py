"""
Settings load from environment variables. Project `.env` is read from the repo
root (next to this package), not the process cwd, so Uvicorn/bot work from any directory.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve repo root: app/core/config.py -> parents: core, app, project
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
# Public path to repo root (bootstrap, dev scripts, self-heal).
REPO_ROOT: Path = _PROJECT_ROOT
# Typical location of project `.env` (same file load_dotenv uses in Settings).
ENV_FILE_PATH: Path = _ENV_FILE
# Project .env wins over pre-set shell vars so USE_REAL_LLM=true in the file is not
# shadowed by a stale `export USE_REAL_LLM=false` from an old session.
_BAD_TERMS = frozenset(("", "API", "dumb", "unknown"))


def _is_bad_term(t: str) -> bool:
    s = (t or "").strip()
    if not s or s in _BAD_TERMS:
        return True
    if s.casefold() == "api":
        return True
    return s.lower() in ("dumb", "unknown")


def _normalize_term_for_subprocesses() -> None:
    t = (os.environ.get("TERM") or "").strip()
    if _is_bad_term(t):
        # Invalid in terminfo — tset(1) / reset(1) / Codex may print "unknown terminal type"
        os.environ["TERM"] = "xterm-256color"
    # Stale entry for a different TERM confuses ncurses
    if "TERMCAP" in os.environ:
        os.environ.pop("TERMCAP", None)


if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE, override=True)
    d = dotenv_values(_ENV_FILE) or {}
    t_from_file: str | None = None
    for key in d:
        if key and str(key).lower() == "term" and d[key] is not None:
            t_from_file = str(d[key]).strip().strip("'\"")
            break
    if t_from_file and not _is_bad_term(t_from_file):
        os.environ["TERM"] = t_from_file
    _normalize_term_for_subprocesses()
else:
    load_dotenv(_ENV_FILE, override=True)
    _normalize_term_for_subprocesses()

# scripts/nexa_next_local_all.sh sets NEXA_NEXT_LOCAL_SIDECAR=1 so the API can boot when .env
# points at Postgres that is not running locally (override uses repo-root SQLite).
if (os.environ.get("NEXA_NEXT_LOCAL_SIDECAR") or "").strip().lower() in ("1", "true", "yes"):
    os.environ["DATABASE_URL"] = f"sqlite:///{(_PROJECT_ROOT / 'overwhelm_reset.db').resolve()}"


def ensure_subprocess_term_env() -> None:
    """Re-run TERM fix (e.g. in dev executor main) after any late env changes."""
    _normalize_term_for_subprocesses()


_EnvFile: str | None = str(_ENV_FILE) if _ENV_FILE.is_file() else None


class Settings(BaseSettings):
    app_name: str = "Nexa"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./overwhelm_reset.db"

    anthropic_api_key: str | None = None
    # Default: current Haiku (3.5 snapshot `claude-3-5-haiku-20241022` is retired on the API)
    anthropic_model: str = "claude-haiku-4-5-20251001"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    use_real_llm: bool = False
    # Optional: documented in .env.example; composer still prefers Anthropic if ANTHROPIC_API_KEY is set
    llm_provider: str | None = None

    default_timezone: str = "America/New_York"
    followup_poll_seconds: int = 30
    default_max_tasks: int = 3
    default_planning_style: str = "gentle"
    api_base_url: str = "http://localhost:8010"

    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None
    # Slack (Events API + Interactions) — optional second channel (Channel Gateway)
    slack_bot_token: str | None = None
    slack_signing_secret: str | None = None

    # Email (inbound webhook + SMTP outbound) — optional channel (Channel Gateway)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    # Shared secret: inbound webhook auth + HMAC for permission links in email.
    email_webhook_secret: str | None = None

    # WhatsApp Cloud API (Meta) — optional channel (Channel Gateway)
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_verify_token: str | None = None
    # Optional: Meta app secret for webhook POST signature verification (X-Hub-Signature-256).
    whatsapp_app_secret: str | None = None

    # SMS (Twilio) — optional channel (Channel Gateway)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    # Apple Messages for Business (provider) — optional channel (Channel Gateway, Phase 11)
    apple_messages_provider_url: str | None = None
    apple_messages_access_token: str | None = None
    apple_messages_business_id: str | None = None
    apple_messages_webhook_secret: str | None = None

    # Enterprise governance (Phase 13) — channel policies, RBAC hooks, audit export
    nexa_governance_enabled: bool = False
    # Optional default org for API/UI when testing governance without SSO (single-tenant).
    nexa_default_organization_id: str | None = None
    # Dev-only: auto-create default org + owner membership on first governance API use (not for production).
    nexa_auto_create_default_org: bool = False

    operator_poll_seconds: int = 20
    operator_auto_run_local_tools: bool = True
    operator_auto_run_dev_executor: bool = True
    # When true, the host Mac runs dev_agent_executor (same DB); the API container skips running it
    # so two processes do not race on the same job. Set via DEV_EXECUTOR_ON_HOST=1 in .env.
    dev_executor_on_host: bool = False
    # When true, the operator loop auto-approves new dev tasks (no manual `approve job #N` from phone).
    # Use only on a trusted machine. Default false so a queued job cannot run without an explicit tap.
    operator_auto_approve_queued_dev_jobs: bool = False
    operator_auto_approve_review: bool = True
    operator_auto_approve_commit_safe: bool = False
    # When true, approves every needs_commit_approval dev job (no title filter). Trusted machine only.
    operator_auto_approve_all_commits: bool = False

    # Autonomous dev worker: one checkout — limit concurrent in-flight dev agent jobs
    dev_agent_max_active_jobs: int = 1
    dev_agent_timeout_seconds: int = 1800
    dev_agent_test_timeout_seconds: int = 600

    # Dev workspace: new project scaffold (`@dev create project <key>`) and /dev workspace
    nexa_workspace_root: str = Field(
        default_factory=lambda: str(Path.home() / "nexa-projects")
    )
    # Workspace posture for prompts: developer = orchestrator-forward (no false "read-only" refusals);
    # regulated = stricter default wording. See NEXA_WORKSPACE_MODE in .env.example.
    nexa_workspace_mode: str = "regulated"
    # When false **and** workspace mode is developer, bounded runtime tools may bypass approval gating
    # (local testing only). Ignored unless NEXA_WORKSPACE_MODE=developer — regulated workspaces fail closed.
    nexa_approvals_enabled: bool = True
    # Optional audit string for access.permission.bypassed events (dev autonomy mode).
    nexa_approval_bypass_reason: str | None = None

    # Governed agent runtime (sessions_spawn / background_heartbeat); optional directory overrides.
    nexa_agent_tools_enabled: bool = False
    nexa_file_watcher_enabled: bool = False
    nexa_reports_dir: str | None = None
    nexa_config_dir: str | None = None
    nexa_memory_dir: str | None = None
    nexa_default_dev_tool: str = "aider"
    nexa_default_dev_mode: str = "autonomous_cli"

    # Required to encrypt per-user API keys in the database (NEXA_SECRET_KEY). Not optional on shared hosts.
    nexa_secret_key: str | None = None

    # Web UI: optional shared secret for `Authorization: Bearer` (in addition to X-User-Id). Unset = bearer not required.
    nexa_web_api_token: str | None = None
    # CORS: comma-separated origins (e.g. the Next dev server).
    nexa_web_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Safe LLM gateway: sanitize / minimize / path allowlist before any external provider call
    safe_llm_mode: bool = True
    safe_llm_max_chars: int = 6000
    safe_llm_allow_raw_code: bool = False
    safe_llm_allowed_roots: str = "app,scripts,tests"
    safe_llm_blocked_patterns: str = ".env,.ssh,credentials,secrets,__pycache__,.venv,node_modules"

    # Public read-only web (safe httpx+BeautifulSoup pipeline, not a browser)
    nexa_web_access_enabled: bool = True
    nexa_web_fetch_timeout_seconds: int = 15
    nexa_web_max_bytes: int = 1_500_000
    nexa_web_max_redirects: int = 5
    nexa_web_respect_robots: bool = True
    nexa_web_user_agent: str = "Nexa/1.0; +https://github.com (public fetch, contact owner)"

    # Optional Playwright-based owner-only public preview (off by default; no login/forms)
    nexa_browser_preview_enabled: bool = False
    nexa_browser_preview_timeout_ms: int = 35_000

    @field_validator("nexa_approvals_enabled", mode="before")
    @classmethod
    def _coerce_approvals_enabled(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return True
        s = str(v).strip().lower()
        if s in ("0", "false", "no", "off", ""):
            return False
        if s in ("1", "true", "yes", "on", "y"):
            return True
        return True

    @field_validator("nexa_workspace_mode", mode="before")
    @classmethod
    def _normalize_workspace_mode(cls, v: object) -> str:
        s = (str(v) if v is not None else "").strip().lower()
        if not s:
            return "regulated"
        if s in ("dev", "development", "developer"):
            return "developer"
        if s == "regulated":
            return "regulated"
        return "regulated"

    @field_validator("nexa_browser_preview_enabled", mode="before")
    @classmethod
    def _coerce_browser_preview_flag(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        s = str(v).strip().lower()
        if s in ("0", "false", "no", "off", ""):
            return False
        if s in ("1", "true", "yes", "on", "y"):
            return True
        return bool(s)

    # Optional tool-based web search (brave, tavily, serpapi) — off by default
    nexa_web_search_enabled: bool = False
    nexa_web_search_provider: str = "none"  # none | brave | tavily | serpapi
    nexa_web_search_api_key: str = ""
    nexa_web_search_max_results: int = 5

    @field_validator("nexa_web_search_enabled", mode="before")
    @classmethod
    def _coerce_web_search_flag(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        s = str(v).strip().lower()
        if s in ("0", "false", "no", "off", ""):
            return False
        if s in ("1", "true", "yes", "on", "y"):
            return True
        return bool(s)

    @field_validator("nexa_web_search_provider", mode="before")
    @classmethod
    def _normalize_search_provider(cls, v: object) -> str:
        t = (str(v) if v is not None else "none").strip().lower() or "none"
        if t in ("", "off", "false", "0"):
            return "none"
        if t in ("brave", "tavily", "serpapi", "none"):
            return t
        return t

    # Local generated documents (.runtime/generated_documents); no automatic cleanup job yet
    nexa_document_retention_days: int = 30

    # Host executor: allowlisted local actions via local_tool jobs + user approval (local_tool_worker).
    # When false, host-executor jobs fail fast on the worker. No effect on the API process unless it enqueues jobs.
    nexa_host_executor_enabled: bool = False
    # Default cwd and path base for file_read / file_write / git_* (repo root by default).
    host_executor_work_root: str = Field(default_factory=lambda: str(_PROJECT_ROOT))
    host_executor_timeout_seconds: int = 120
    host_executor_max_file_bytes: int = 262_144
    host_executor_read_multiple_max_files: int = 20
    # Cap for bundling file text into on-demand LLM analysis (no storage / indexing).
    host_executor_intel_max_prompt_chars: int = 48_000
    # Workspace registry: when strict, paths must fall under explicit /workspace roots (no compat default root).
    nexa_workspace_strict: bool = False
    # When true, host_executor enforces access_permissions + workspace roots for jobs that include user_id.
    nexa_access_permissions_enforced: bool = False
    # Structural safety policy: reject host payloads whose stamped policy version/hash disagrees with this process.
    nexa_safety_policy_strict: bool = False
    # When true, outbound HTTP(S) from web_access requires network_external_send grants (see access_permissions).
    nexa_network_external_send_enforced: bool = False
    # When true, outbound bodies that look like secrets are blocked at the egress gate (see outbound_request_gate).
    nexa_secret_egress_enforced: bool = False
    # When true, sending secret-like content off-machine requires explicit user confirmation (enforcement_pipeline).
    nexa_sensitive_external_confirmation_required: bool = False
    # When true, emit DB audit rows for safety.enforcement.path (host executor etc.); can be high volume.
    nexa_audit_enforcement_paths: bool = False

    # Cursor Cloud Agents API (Phase 1) — optional coding executor; see docs/cloud-agent API.
    cursor_enabled: bool = False
    cursor_api_key: str | None = None
    cursor_api_base: str = "https://api.cursor.com"
    cursor_default_model: str = "composer-2"
    # Required for real runs: HTTPS GitHub repo URL Nexa is allowed to target.
    cursor_default_repo_url: str | None = None
    cursor_default_branch: str = "main"
    # Comma-separated URL prefixes; empty = any repo (still requires default repo URL).
    cursor_allowed_repo_urls: str = ""
    cursor_auto_create_pr: bool = False
    cursor_http_timeout_seconds: float = 120.0
    cursor_poll_interval_seconds: float = 3.0
    cursor_max_poll_iterations: int = 60

    # Dev-only: allow hard DELETE for Mission Control cleanup APIs (assignments / jobs).
    nexa_dev_allow_hard_delete: bool = False
    # Dev-only: allow POST /mission-control/database/purge-sql (hard-delete MC-related rows for user).
    nexa_mission_control_sql_purge: bool = False

    # --- Nexa Next (gateway runtime + privacy firewall; incremental rollout) ---
    nexa_privacy_firewall_enabled: bool = True
    nexa_redact_pii_before_external_api: bool = True
    nexa_block_secrets_to_external_api: bool = True
    # Phase 10 — production hardening
    nexa_disable_external_calls: bool = False
    nexa_provider_rate_limit_per_minute: int = 120
    nexa_admin_endpoints_enabled: bool = False

    # Phase 11 — production stabilization
    nexa_release_version: str = "phase-11"
    nexa_provider_timeout_seconds: float = 15.0
    nexa_provider_max_retries: int = 3
    nexa_mission_max_runtime_seconds: int = 60
    nexa_data_retention_days: int = 7
    nexa_retention_sweep_interval_seconds: int = 3600

    # Phase 13 — strict privacy lockdown (external providers off; local_stub only)
    nexa_strict_privacy_mode: bool = False

    # Phase 18 — post-provider scan uses ingress-style detection when true (paranoid / audit).
    nexa_detection_strict_mode: bool = False

    # Phase 19 — user-facing privacy stance (standard | strict | paranoid).
    nexa_user_privacy_mode: str = "standard"

    # Phase 22 — OpenClaw parity (memory, autonomy, local-first).
    nexa_memory_layer_enabled: bool = True
    nexa_local_first: bool = False
    nexa_ollama_base_url: str | None = None
    nexa_mission_parallel_tasks: bool = False

    # Phase 23 — AI dev OS (workspace commands, allowlist).
    nexa_dev_allowed_commands: str = (
        "git status,git diff,git branch,git log --oneline -n 20,"
        "npm test,npm run test,pytest,python -m pytest"
    )
    # Comma-separated absolute path prefixes; empty → nexa_workspace_root + repo root (see workspace validator).
    nexa_dev_workspace_roots: str = ""
    nexa_dev_command_timeout_seconds: int = 180

    @field_validator("nexa_user_privacy_mode", mode="before")
    @classmethod
    def _normalize_nexa_user_privacy_mode(cls, v: object) -> str:
        x = (str(v) if v is not None else "standard").strip().lower()
        return x if x in ("standard", "strict", "paranoid") else "standard"

    model_config = SettingsConfigDict(
        env_file=_EnvFile,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def print_local_service_urls() -> None:
    """Log human-facing URLs for this API process (Uvicorn on the host or Docker)."""
    s = get_settings()
    base = s.api_base_url.rstrip("/")
    p = s.api_v1_prefix
    print("--- Local service URLs ---", flush=True)
    print(f"  Backend / health     {base}{p}/health", flush=True)
    print(f"  System health        {base}{p}/system/health", flush=True)
    print(f"  API docs (Swagger)   {base}/docs", flush=True)
    print(f"  ReDoc                {base}/redoc", flush=True)
    print(f"  Dashboard            {base}/dashboard", flush=True)
    print("  Telegram bot         no local URL; chat in the Telegram app", flush=True)
    print(f"  Email inbound        {base}{p}/email/inbound  (X-Email-Webhook-Secret)", flush=True)
    print(f"  WhatsApp webhook     {base}{p}/whatsapp/webhook  (GET verify + POST)", flush=True)
    print(f"  SMS inbound (Twilio) {base}{p}/sms/inbound  (POST form)", flush=True)
    print(
        f"  Apple Messages        {base}{p}/apple-messages/inbound  (POST JSON)",
        flush=True,
    )
    print("--------------------------", flush=True)


def print_llm_debug_banner() -> None:
    """Log env-driven LLM flags once at process startup (API or bot)."""
    import logging

    s = get_settings()
    log = logging.getLogger("nexa.settings")
    log.info(
        "LLM settings use_real_llm=%s anthropic_configured=%s openai_configured=%s llm_provider=%s",
        s.use_real_llm,
        bool(s.anthropic_api_key),
        bool(s.openai_api_key),
        (s.llm_provider or "").strip(),
    )
    if not s.use_real_llm and (s.anthropic_api_key or s.openai_api_key):
        log.warning(
            "API keys present but USE_REAL_LLM is false; set USE_REAL_LLM=true in .env and restart."
        )
