"""
Settings load from environment variables. Project `.env` is read from the repo
root (next to this package), not the process cwd, so Uvicorn/bot work from any directory.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from pydantic import Field, field_validator, model_validator
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

# Phase 36 — AETHOS_* → NEXA_* before Settings() reads os.environ (see app/core/aethos_env.py).
from app.core.aethos_env import apply_aethos_env_aliases

apply_aethos_env_aliases()

# scripts/nexa_next_local_all.sh sets NEXA_NEXT_LOCAL_SIDECAR=1 so the API can boot when .env
# points at Postgres that is not running locally (override uses repo-root SQLite).
if (os.environ.get("NEXA_NEXT_LOCAL_SIDECAR") or "").strip().lower() in ("1", "true", "yes"):
    os.environ["DATABASE_URL"] = f"sqlite:///{(_PROJECT_ROOT / 'overwhelm_reset.db').resolve()}"


def ensure_subprocess_term_env() -> None:
    """Re-run TERM fix (e.g. in dev executor main) after any late env changes."""
    _normalize_term_for_subprocesses()


_EnvFile: str | None = str(_ENV_FILE) if _ENV_FILE.is_file() else None


class Settings(BaseSettings):
    app_name: str = "AethOS"
    # User-facing branding (optional overrides via AETHOS_BRAND_* env).
    aethos_brand_name: str = "AethOS"
    aethos_brand_tagline: str = "The Agentic Operating System"
    aethos_brand_prompt: str | None = None
    app_env: str = "development"
    debug: bool = True
    # When true, API boot uses JSON log lines (one object per line) for aggregation; see app.services.logging
    log_json_format: bool = False
    # Week 4 — sub-agent registry (in-memory, single-worker; see docs/AGENT_ORCHESTRATION.md)
    nexa_agent_orchestration_enabled: bool = False
    nexa_agent_max_per_chat: int = 20
    nexa_agent_idle_timeout_seconds: int = 3600
    # Phase 37 — default trusted flag for API `/agents/create` when request omits explicit approval.
    nexa_agent_auto_approve: bool = False
    # Phase 37 — optional asyncio supervisor loop (registry + audit health checks).
    nexa_agent_monitoring_enabled: bool = False
    nexa_agent_monitor_interval_seconds: int = 30
    # When true with orchestration, sub-agent host payloads run via execute_payload in-process (audit log).
    nexa_agent_orchestration_autoqueue: bool = False
    # Week 5 — in-process rate limits (single-worker; see sub_agent_rate_limit)
    nexa_agent_rate_limit_per_agent: int = 30
    nexa_agent_rate_limit_per_chat: int = 80
    nexa_agent_rate_limit_per_domain: int = 40
    nexa_agent_rate_limit_window_seconds: int = 60
    # Week 5 — autoqueue allowlists (empty chats = any chat). Domain list lowercase names.
    nexa_agent_autoqueue_allowlist_chats: str = ""
    nexa_agent_autoqueue_allowlist_domains: str = "git"
    # After N successful in-process autoqueue executions per agent, force approval queue (0 = off).
    nexa_agent_autoqueue_require_approval_after: int = 0
    # Run idle-agent cleanup at most this often during orchestration turns (seconds).
    nexa_agent_cleanup_interval_seconds: int = 300
    # When true (default), bare @mention runs a safe default action ("status") instead of "ready" text.
    nexa_sub_agent_auto_execute: bool = True
    # Week 5.5 — skip Jobs approval for trusted chat/domain/sub-agent (host executor paths)
    nexa_auto_approve_enabled: bool = False
    nexa_auto_approve_chats: str = ""
    nexa_auto_approve_domains: str = "git"
    nexa_auto_approve_log_only: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./overwhelm_reset.db"

    anthropic_api_key: str | None = None
    # Default: current Haiku (3.5 snapshot `claude-3-5-haiku-20241022` is retired on the API)
    anthropic_model: str = "claude-haiku-4-5-20251001"
    # Optional Pro tier overrides when ``nexa_ext.routing`` + ``smart_routing`` license is active.
    nexa_pro_anthropic_strong_model: str | None = None
    nexa_pro_anthropic_fast_model: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    use_real_llm: bool = False
    # Optional: documented in .env.example; composer still prefers Anthropic if ANTHROPIC_API_KEY is set
    llm_provider: str | None = None
    # Phase 11 — multi-provider primary LLM (orchestrator / safe_llm path)
    # auto = prefer anthropic → openai → deepseek → openrouter → ollama when keys allow
    nexa_llm_provider: str = "auto"
    nexa_llm_model: str | None = None
    nexa_llm_api_key: str | None = None
    nexa_llm_base_url: str | None = None
    nexa_llm_fallback_providers: str = ""
    nexa_llm_temperature: float = 0.7
    nexa_llm_max_tokens: int = 4096
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str | None = None

    default_timezone: str = "America/New_York"
    followup_poll_seconds: int = 30
    default_max_tasks: int = 3
    default_planning_style: str = "gentle"
    api_base_url: str = "http://localhost:8010"

    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None
    # When True (default), FastAPI lifespan starts Telegram long polling in a background thread when
    # TELEGRAM_BOT_TOKEN is set (same process as ``nexa serve``). Set false if you run
    # ``python -m app.bot.telegram_bot`` in a separate terminal to avoid duplicate polling.
    nexa_telegram_embed_with_api: bool = True
    # Slack (Events API + Interactions + optional Socket Mode) — Channel Gateway / Phase 12.1
    slack_bot_token: str | None = None
    slack_app_token: str | None = None  # xapp- — Socket Mode (Bolt); omit if using HTTP Events only
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

    # Autonomous dev worker: one checkout — limit concurrent in-flight development tasks
    dev_agent_max_active_jobs: int = 1
    dev_agent_timeout_seconds: int = 1800
    dev_agent_test_timeout_seconds: int = 600

    # Dev workspace: new project scaffold (ask Nexa to create a project for a key) and /dev workspace
    nexa_workspace_root: str = Field(
        default_factory=lambda: str(Path.home() / "aethos-projects")
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
    # Telegram voice notes — transcription pipeline (Phase 53 stub until wired).
    nexa_voice_enabled: bool = False
    nexa_voice_transcribe_provider: str = "local"

    # Phase 54 — sandbox / vault / egress / resource caps (MVP policy gates).
    nexa_sandbox_mode: str = "process"
    nexa_require_sandbox_for_skills: bool = False
    # Phase 6 — pluggable skills (ClawHub-style); see docs/SKILLS_SYSTEM.md
    nexa_clawhub_api_base: str = "https://clawhub.com/api/v1"
    # Phase 17 — marketplace installs (ZIP/yaml under this directory)
    nexa_clawhub_enabled: bool = True
    nexa_clawhub_skill_root: str = Field(default_factory=lambda: str(REPO_ROOT / "data" / "skills"))
    nexa_clawhub_trusted_publishers: str = ""
    nexa_clawhub_require_signature: bool = False
    nexa_clawhub_auto_update: bool = False
    nexa_clawhub_require_install_approval: bool = False

    # Phase 18a — multi-modal (vision / audio / image gen); provider wiring in later sub-phases.
    nexa_multimodal_enabled: bool = False
    nexa_multimodal_vision_enabled: bool = False
    nexa_multimodal_vision_provider: str = "auto"
    nexa_multimodal_vision_model: str | None = None
    nexa_audio_input_enabled: bool = False
    nexa_audio_transcription_provider: str = "openai"
    nexa_audio_output_enabled: bool = False
    nexa_image_gen_enabled: bool = False
    nexa_image_gen_provider: str = "openai"  # openai | replicate | local_sd
    # Phase 18d — image generation shortcut (with NEXA_MULTIMODAL_ENABLED).
    nexa_multimodal_image_enabled: bool = False
    nexa_openai_image_model: str = "dall-e-3"  # dall-e-2 | dall-e-3
    nexa_replicate_api_token: str | None = None
    nexa_replicate_image_version: str | None = None  # prediction model version hash
    nexa_local_sd_url: str | None = None  # e.g. http://127.0.0.1:7860/sdapi/v1/txt2img (A1111)
    nexa_multimodal_max_image_mb: int = 10
    nexa_multimodal_max_audio_seconds: int = 300
    nexa_multimodal_max_image_side_px: int = 8192
    nexa_multimodal_temp_ttl_seconds: int = 3600
    nexa_multimodal_strip_image_metadata: bool = False
    # Google Gemini (REST :generateContent) — optional; used when `nexa_multimodal_vision_provider=gemini`.
    nexa_gemini_api_key: str | None = None
    # Phase 18c — audio (STT/TTS); when true, enables STT+TTS with NEXA_MULTIMODAL_ENABLED (or use the granular flags below).
    nexa_multimodal_audio_enabled: bool = False
    nexa_multimodal_max_audio_mb: int = 25
    nexa_audio_output_provider: str = "openai"  # openai | elevenlabs
    nexa_openai_tts_model: str = "tts-1"
    nexa_openai_tts_voice: str = "alloy"
    nexa_elevenlabs_api_key: str | None = None
    nexa_elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"

    nexa_plugin_skills_root: str = Field(
        default_factory=lambda: str(REPO_ROOT / "data" / "aethos_plugin_skills")
    )
    nexa_credential_vault_provider: str = "local"
    nexa_network_egress_mode: str = "allowlist"
    nexa_network_allowed_hosts: str = (
        "api.openai.com,api.anthropic.com,api.deepseek.com,openrouter.ai,localhost,127.0.0.1,"
        "api.telegram.org,api.search.brave.com,api.tavily.com,serpapi.com,"
        "www.googleapis.com,generativelanguage.googleapis.com,api.elevenlabs.io,api.replicate.com,"
        "api.twitter.com,api.x.com,graph.facebook.com,graph.instagram.com,api.linkedin.com,"
        "open.tiktokapis.com,open-upload.tiktokapis.com"
    )
    nexa_resource_max_cpu_percent: float = 0.0
    nexa_resource_max_memory_mb: int = 0
    nexa_resource_max_gpu_memory_mb: int = 0
    nexa_resource_max_parallel_tasks: int = 0
    nexa_default_dev_tool: str = "aider"
    nexa_default_dev_mode: str = "autonomous_cli"

    # Required to encrypt per-user API keys in the database (NEXA_SECRET_KEY). Not optional on shared hosts.
    nexa_secret_key: str | None = None

    # Open-core / optional commercial tier — signed license JWT-like token (see app/services/licensing).
    # Without NEXA_LICENSE_PUBLIC_KEY_PEM, license strings are ignored (OSS default).
    nexa_license_key: str | None = None
    nexa_license_public_key_pem: str | None = None
    # Comma-separated enterprise capability keys (same names as app.core.feature_flags.ENTERPRISE_FEATURES)
    # or raw license feature IDs — grants without a signed token (pilots / contract installs).
    nexa_enterprise_granted_features: str = ""
    # When true with app_env=development, enterprise gates unlock for integration testing (never use in prod).
    nexa_open_core_dev_unlock: bool = False
    # When true, selected APIs enforce enterprise flags (e.g. second agent-org). Default false preserves OSS UX.
    nexa_enforce_enterprise_gates: bool = False

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
    nexa_web_user_agent: str = "AethOS/1.0; +https://github.com (public fetch, contact owner)"

    # Phase 21 — HTTP scraping (httpx + BeautifulSoup + lxml; API uses NEXA_CRON_API_TOKEN)
    nexa_scraping_enabled: bool = True
    nexa_scraping_max_pages: int = 10
    nexa_scraping_timeout_seconds: int = 30
    nexa_scraping_rate_limit_per_minute: int = 60
    # JSON array, or "UA1||UA2" (double-pipe) when not JSON; empty → built-in default pool
    nexa_scraping_user_agents: str = ""
    nexa_scraping_proxy_url: str | None = None
    nexa_scraping_stealth_mode: bool = True

    # Phase 22 — social media automation (opt-in; secrets via env)
    nexa_social_enabled: bool = False
    nexa_twitter_enabled: bool = False
    twitter_api_key: str | None = None
    twitter_api_secret: str | None = None
    twitter_access_token: str | None = None
    twitter_access_secret: str | None = None
    twitter_bearer_token: str | None = None
    nexa_linkedin_enabled: bool = False
    linkedin_access_token: str | None = None
    linkedin_person_urn: str | None = None
    nexa_facebook_enabled: bool = False
    facebook_page_access_token: str | None = None
    facebook_page_id: str | None = None
    # Phase 24 — Instagram feed (Graph ``media`` + ``media_publish``). Token may match Page token.
    nexa_instagram_enabled: bool = False
    instagram_page_access_token: str | None = None
    instagram_business_account_id: str | None = None
    # Phase 24 — TikTok Content Posting (Direct Post FILE_UPLOAD + status fetch)
    nexa_tiktok_enabled: bool = False
    tiktok_access_token: str | None = None
    tiktok_open_id: str | None = None
    # Required values depend on creator / app audit — default safe for sandbox unaudited apps
    tiktok_privacy_level: str = "SELF_ONLY"
    nexa_social_rate_limit_per_hour: int = 50
    nexa_social_max_media_size_mb: int = 10

    # Optional Playwright-based owner-only public preview (off by default; no login/forms)
    nexa_browser_preview_enabled: bool = False
    nexa_browser_preview_timeout_ms: int = 35_000
    # Playwright click / form fill on allowlisted public URLs (still no logins; off by default)
    nexa_browser_automation_enabled: bool = False
    # Phase 14 — async Playwright (CDP/Chromium) for skills, REST API, NL (Docker: install browsers in image).
    nexa_browser_enabled: bool = True
    nexa_browser_headless: bool = True
    nexa_browser_timeout: int = 30000  # milliseconds (env: NEXA_BROWSER_TIMEOUT)
    nexa_browser_screenshot_dir: str = Field(
        default_factory=lambda: str(REPO_ROOT / "data" / "screenshots"),
    )

    @field_validator("nexa_browser_screenshot_dir", mode="before")
    @classmethod
    def _browser_screenshot_dir_fallback(cls, v: object) -> str:
        s = (str(v) if v is not None else "").strip()
        if not s:
            return str(REPO_ROOT / "data" / "screenshots")
        return s

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
    # Batch allowlisted host steps in one job (``host_action: chain``); see ~/.aethos/docs/handoffs/WEEK2_HOST_ACTION_CHAINS.md (local handoff pack)
    nexa_host_executor_chain_enabled: bool = False
    nexa_host_executor_chain_max_steps: int = 10
    # Comma-separated inner host_action names; empty → default set in host_executor_chain.DEFAULT_CHAIN_INNER_ALLOWED
    nexa_host_executor_chain_allowed_actions: str = ""
    # NL → readme+commit+push chain (narrow phrases); requires chain + host executor enabled.
    nexa_nl_to_chain_enabled: bool = False
    # Phase 58 — after external-exec prefs, run bounded `railway` + `git status` on registered workspace (never deploy).
    nexa_external_execution_runner_enabled: bool = True
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
    # Phase 38 — token economy (provider gateway + Mission Control)
    nexa_token_budget_per_request: int = 8000
    nexa_token_budget_per_day: int = 100_000
    nexa_cost_budget_per_day_usd: float = 5.0
    nexa_block_over_token_budget: bool = True
    nexa_mission_max_runtime_seconds: int = 60
    nexa_data_retention_days: int = 7
    nexa_retention_sweep_interval_seconds: int = 3600
    # Phase 27 — Mission Control projects & tasks (dedicated SQLite under NEXA_DATA_DIR)
    nexa_projects_enabled: bool = True
    nexa_data_dir: str = Field(default_factory=lambda: str(REPO_ROOT / "data"))
    # Task checkout (claim) auto-release when lock age exceeds this (seconds).
    nexa_task_lock_timeout_seconds: int = 3600
    # Phase 28 — per-member work-hour budgets (token metering; SQLite under NEXA_DATA_DIR/budget.db).
    nexa_budget_enabled: bool = True
    nexa_budget_default_monthly_limit: int = 1_000_000
    nexa_budget_reset_day: int = 1
    # Phase 29 — multi-tenant workspaces, roles, teams (SQLite rbac.db under NEXA_DATA_DIR).
    nexa_rbac_enabled: bool = False
    # Phase 30 — mobile app JWT lifetime (hours).
    nexa_mobile_token_ttl_hours: int = 168

    # Phase 13 — strict privacy lockdown (external providers off; local_stub only)
    nexa_strict_privacy_mode: bool = False

    # Phase 18 — post-provider scan uses ingress-style detection when true (paranoid / audit).
    nexa_detection_strict_mode: bool = False

    # Phase 19 — user-facing privacy stance (standard | strict | paranoid).
    nexa_user_privacy_mode: str = "standard"

    # Phase 33 — production posture (quiet logs, no experimental tooling hooks).
    nexa_production_mode: bool = False

    # Phase 22 — OpenClaw parity (memory, autonomy, local-first).
    nexa_memory_layer_enabled: bool = True
    # Phase 55 — reduce generic “next steps” / appendix tone for dev-analysis chat.
    nexa_decisive_dev_chat: bool = True
    # Phase 56 — when execution confidence is “medium”, ask before auto-running a dev mission.
    nexa_execution_confirm_medium: bool = True
    # P0 — autonomous operator: act on clear intent; fewer confirmations (pairs with external_execution_session).
    nexa_operator_mode: bool = False
    # Phase Next — mutating operator actions (require host executor + operator mode).
    nexa_operator_allow_write: bool = False
    nexa_operator_allow_deploy: bool = False
    nexa_operator_auto_retry: bool = False
    # When operator mode is on, prepend a short “mission accepted” block to operator / execution-loop replies.
    nexa_operator_proactive_intro: bool = True
    # When operator mode is on, read and append ``PULSE.md`` standing orders (and related live-progress lines).
    nexa_pulse_injection: bool = True
    # When operator mode is on, treat short replies like “approve” / “go” as full external-exec prefs (fewer follow-up prompts).
    nexa_operator_autonomous_external_flow: bool = False
    # When operator mode is on, shorten access/Railway copy, bypass external-exec access gate, and scrub nag phrases from operator/execution replies.
    nexa_operator_zero_nag: bool = True
    # Hold pasted provider tokens in this API process RAM only (bounded CLI auth); never logged or echoed.
    nexa_operator_session_credential_reuse: bool = True
    # Ultra-short operator / execution-loop replies: collapse progress prose and strip boilerplate (not fenced CLI output).
    nexa_operator_precise_short_responses: bool = True
    # Run allowlisted CLIs (vercel, gh, railway, git in host executor) via bash -lc after sourcing nvm.sh + rc files.
    nexa_operator_cli_profile_shell: bool = True
    # Optional absolute binaries when PATH/nvm is invisible to the worker (set from `which vercel` etc.).
    nexa_operator_cli_vercel_abs: str = ""
    nexa_operator_cli_gh_abs: str = ""
    nexa_operator_cli_git_abs: str = ""
    nexa_operator_cli_railway_abs: str = ""
    # When True, append Docker/host login instructions if Vercel/gh fail with "not logged in" patterns.
    nexa_operator_cli_auth_guidance: bool = True
    # Shown in guidance text for docker exec examples (override if your compose container name differs).
    nexa_operator_guidance_docker_container: str = "nexa-api"
    # Structured workspace intelligence (file-based context under data/nexa_workspace/).
    nexa_workspace_intelligence_enabled: bool = False
    nexa_workspace_intel_root: str = ""
    nexa_workspace_intel_default_token_budget: int = 1500
    nexa_workspace_intel_hard_token_budget: int = 3000
    # Infra / deployment — prepend honesty banner when chat implies verified cloud work without proof.
    nexa_execution_truth_guard_enabled: bool = True
    nexa_local_first: bool = False
    nexa_ollama_base_url: str | None = None
    # Phase 39 — local Ollama when NEXA_LOCAL_FIRST routes tools away from remote APIs
    nexa_ollama_enabled: bool = False
    nexa_ollama_default_model: str = "llama3"
    nexa_mission_parallel_tasks: bool = False
    # When True with SQLite, allow parallel agent waves (dev-only; session-per-thread).
    nexa_mission_parallel_allow_sqlite: bool = False
    # Phase 39 — periodic autonomy heartbeat (OpenClaw-style background tick)
    nexa_heartbeat_enabled: bool = False
    nexa_heartbeat_interval_seconds: int = 300
    # Phase 42 — Ollama HTTP embeddings (requires ``nexa_ollama_enabled`` + reachable Ollama).
    nexa_ollama_embeddings_enabled: bool = False
    # Phase 15 — active memory (chunked cosine recall; uses ``embed_text_primary`` — optional Ollama).
    nexa_active_memory_enabled: bool = False
    nexa_active_memory_always: bool = False
    nexa_active_memory_top_k: int = 8
    nexa_active_memory_min_score: float = 0.12
    nexa_active_memory_max_chars: int = 4000
    nexa_active_memory_chunk_chars: int = 800
    nexa_active_memory_chunk_overlap: int = 100
    nexa_active_memory_max_entries_scan: int = 200
    nexa_active_memory_ingest_enabled: bool = True

    # Phase 16a — gateway `/delegate` + REST `/orchestration/delegate` (agent_team spawn groups).
    nexa_orchestration_enabled: bool = False
    nexa_orchestration_max_delegates: int = 5
    nexa_orch_max_parallel_agents: int = 3
    nexa_orch_delegation_timeout_ms: int = 30000
    nexa_orch_require_approval: bool = False

    # Discord bot (optional ``discord.py`` package).
    nexa_discord_enabled: bool = False
    nexa_discord_bot_token: str = ""
    nexa_discord_app_user_id: str = ""
    # Phase 13 — cron scheduling + proactive automation (AsyncIOScheduler + SQLite job store).
    nexa_cron_enabled: bool = True
    nexa_cron_default_timezone: str = "UTC"
    nexa_cron_job_store: str = Field(
        default_factory=lambda: f"sqlite:///{REPO_ROOT}/data/aethos_cron_jobs.sqlite",
    )
    # Bearer token for Telegram/Slack/CLI → POST /api/v1/cron/* (set in production).
    nexa_cron_api_token: str | None = None

    # Phase 12.1 — Slack Bolt Socket Mode (background task in API lifespan when enabled).
    nexa_slack_enabled: bool = False
    # When True, reaction_added events are turned into gateway prompts (can be noisy).
    nexa_slack_reactions_enabled: bool = False
    # Slack: use NexaGateway route_inbound instead of legacy channel gateway pipeline.
    nexa_slack_route_inbound: bool = False
    # Autonomy — tighten scheduler + heartbeat expectations (documentary; gates optional hooks).
    nexa_autonomous_mode: bool = False
    # Phase 43 — when True with ``nexa_autonomous_mode``, DB long-running ticks invoke the gateway.
    nexa_long_running_gateway_tick: bool = False
    # Phase 45 — autonomous task execution (gateway) per heartbeat / direct API.
    nexa_autonomy_execution_enabled: bool = True
    nexa_autonomy_max_tasks_per_cycle: int = 5
    nexa_autonomy_max_users_per_heartbeat: int = 12
    # Phase 46 — enqueue higher-level goals as autonomous tasks.
    nexa_goal_engine_enabled: bool = False
    # Phase 47 — autonomy stability (pending-queue depth + daily token ceiling).
    nexa_autonomy_max_pending_tasks: int = 48
    nexa_autonomy_daily_token_ceiling: int = 400_000

    # Phase 23 — AI dev OS (workspace commands, allowlist).
    nexa_dev_allowed_commands: str = (
        "git status,git status --porcelain,git diff,git diff --name-only,"
        "git branch,git log --oneline -n 20,"
        "npm test,npm run test,pytest,python -m pytest"
    )
    # Comma-separated absolute path prefixes; empty → nexa_workspace_root + repo root (see workspace validator).
    nexa_dev_workspace_roots: str = ""
    nexa_dev_command_timeout_seconds: int = 180

    # Phase 24 — coding-agent adapters + GitHub PR stub
    nexa_aider_enabled: bool = True
    nexa_aider_command: str = "aider"
    nexa_cursor_agent_enabled: bool = False
    cursor_api_key: str | None = None
    nexa_cursor_agent_require_cost_budget: bool = True
    nexa_cursor_agent_max_cost_usd: float = 2.0
    nexa_claude_code_enabled: bool = False
    nexa_claude_code_command: str = "claude"
    nexa_codex_enabled: bool = False
    nexa_codex_command: str = "codex"
    nexa_github_pr_enabled: bool = False
    # Default base branch for REST PRs (Phase 46).
    nexa_github_default_branch: str = "main"
    github_token: str | None = None

    # Automated GitHub PR reviews (webhook + manual API; optional LLM summary)
    nexa_pr_review_enabled: bool = False
    nexa_pr_review_webhook_secret: str | None = None
    nexa_pr_review_poll_interval: int = 60
    nexa_pr_review_auto_approve: bool = False
    nexa_pr_review_max_files: int = 50
    # Comma-separated glob/substrings — parsed by app.services.pr_review (fnmatch + basename).
    nexa_pr_review_ignore_patterns: str = (
        "*.md,*.txt,*.lock,package-lock.json,yarn.lock,*.min.js"
    )

    # Phase 51 — AethOS Cloud (hosted SaaS): Stripe billing + optional JWT registration/login.
    # JWTs use NEXA_SECRET_KEY (see ensure_nexa_secret_key); set STRIPE_* when enabling billing routes.
    aethos_cloud_enabled: bool = False
    stripe_api_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id_pro: str = ""
    stripe_price_id_business: str = ""
    stripe_price_id_enterprise: str = ""
    # Public URLs for dashboards / redirects (optional documentation defaults).
    cloud_api_url: str = ""
    cloud_web_url: str = ""
    redis_url: str | None = None
    access_token_expire_days: int = 30

    @field_validator("nexa_user_privacy_mode", mode="before")
    @classmethod
    def _normalize_nexa_user_privacy_mode(cls, v: object) -> str:
        x = (str(v) if v is not None else "standard").strip().lower()
        return x if x in ("standard", "strict", "paranoid") else "standard"

    @field_validator("aethos_brand_prompt", mode="before")
    @classmethod
    def _normalize_aethos_brand_prompt(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("nexa_budget_reset_day", mode="before")
    @classmethod
    def _clamp_nexa_budget_reset_day(cls, v: object) -> int:
        try:
            n = int(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 1
        return max(1, min(28, n))

    @model_validator(mode="after")
    def _phase33_production_lock(self) -> Settings:
        """When NEXA_PRODUCTION_MODE is set, disable debug tooling surfaces unsuitable for prod."""
        import os

        if not self.nexa_production_mode:
            return self
        object.__setattr__(self, "debug", False)
        _py = (os.environ.get("NEXA_PYTEST") or "").strip().lower() in ("1", "true", "yes")
        # Under pytest, keep NEXA_AGENT_TOOLS_ENABLED / NEXA_BROWSER_PREVIEW_ENABLED from .env (Phase 33 lock).
        if not _py:
            object.__setattr__(self, "nexa_agent_tools_enabled", False)
        if not _py:
            object.__setattr__(self, "nexa_browser_preview_enabled", False)
        object.__setattr__(self, "nexa_file_watcher_enabled", False)
        return self

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
    print(
        f"  GitHub PR review      {base}{p}/pr-review/webhook  (POST; NEXA_PR_REVIEW_ENABLED)",
        flush=True,
    )
    print("--------------------------", flush=True)


def print_llm_debug_banner() -> None:
    """Log env-driven LLM flags once at process startup (API or bot)."""
    import logging

    s = get_settings()
    log = logging.getLogger("nexa.settings")
    log.info(
        "LLM settings use_real_llm=%s anthropic_configured=%s openai_configured=%s llm_provider=%s nexa_llm_provider=%s",
        s.use_real_llm,
        bool(s.anthropic_api_key),
        bool(s.openai_api_key),
        (s.llm_provider or "").strip(),
        (s.nexa_llm_provider or "").strip(),
    )
    if not s.use_real_llm and (s.anthropic_api_key or s.openai_api_key):
        log.warning(
            "API keys present but USE_REAL_LLM is false; set USE_REAL_LLM=true in .env and restart."
        )
