"""Detect installed deployment CLIs and infer hints from project files / frameworks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


class DeploymentDetector:
    """
    Known CLIs — binaries checked with :func:`shutil.which`.

    Deploy commands use argv lists (no shell) except ``deploy_shell`` (Heroku git push).
    """

    #: Priority when auto-deploy tries multiple PATH-installed tools (first wins in executor).
    PRIORITY: tuple[str, ...] = (
        "vercel",
        "railway",
        "fly",
        "netlify",
        "cloudflare",
        "deno",
        "gcloud",
    )

    CLI_REGISTRY: dict[str, dict[str, Any]] = {
        "vercel": {
            "binary": "vercel",
            "deploy_argv": ["vercel", "--prod", "--yes"],
            "deploy_argv_preview": ["vercel", "--yes"],
            "login_hint": "vercel login",
            "url_pattern": r"https://[^\s\"']+\.vercel\.app[^\s\"']*",
        },
        "railway": {
            "binary": "railway",
            "deploy_argv": ["railway", "up"],
            "deploy_argv_preview": ["railway", "up"],
            "login_hint": "railway login",
            "url_pattern": r"https://[^\s\"']+\.(?:up\.railway\.app|railway\.app)[^\s\"']*",
        },
        "aws": {
            "binary": "aws",
            "manual_only": True,
            "login_hint": "aws configure",
            "url_pattern": r"https://[^\s\"']+\.amazonaws\.com[^\s\"']*",
            "note": "No single generic AWS deploy; use SAM/CDK/ECS or your pipeline.",
        },
        "gcloud": {
            "binary": "gcloud",
            "deploy_argv": ["gcloud", "app", "deploy", "--quiet"],
            "deploy_argv_preview": ["gcloud", "app", "deploy", "--quiet"],
            "login_hint": "gcloud auth login",
            "url_pattern": r"https://[^\s\"']+\.appspot\.com[^\s\"']*",
            "note": "Requires app.yaml for App Engine.",
        },
        "fly": {
            "binary": "flyctl",
            "deploy_argv": ["flyctl", "deploy"],
            "deploy_argv_preview": ["flyctl", "deploy"],
            "login_hint": "flyctl auth login",
            "url_pattern": r"https://[^\s\"']+\.fly\.dev[^\s\"']*",
        },
        "netlify": {
            "binary": "netlify",
            "deploy_argv": ["netlify", "deploy", "--prod"],
            "deploy_argv_preview": ["netlify", "deploy"],
            "login_hint": "netlify login",
            "url_pattern": r"https://[^\s\"']+\.netlify\.app[^\s\"']*",
        },
        "heroku": {
            "binary": "heroku",
            "deploy_shell": "git push heroku HEAD:main",
            "login_hint": "heroku login",
            "url_pattern": r"https://[^\s\"']+\.herokuapp\.com[^\s\"']*",
            "note": "Requires git remote `heroku`; uses shell. Preview not supported.",
        },
        "cloudflare": {
            "binary": "wrangler",
            "deploy_argv": ["wrangler", "deploy"],
            "deploy_argv_preview": ["wrangler", "deploy"],
            "login_hint": "wrangler login",
            "url_pattern": r"https://[^\s\"']+\.(?:pages\.dev|workers\.dev)[^\s\"']*",
        },
        "deno": {
            "binary": "deno",
            "deploy_argv": ["deno", "deploy"],
            "deploy_argv_preview": ["deno", "deploy"],
            "login_hint": "deno deploy login",
            "url_pattern": r"https://[^\s\"']+\.deno\.dev[^\s\"']*",
        },
    }

    FILE_HINTS: dict[str, tuple[str, ...]] = {
        "vercel.json": ("vercel",),
        "vercel.toml": ("vercel",),
        "railway.json": ("railway",),
        "railway.toml": ("railway",),
        "fly.toml": ("fly",),
        "netlify.toml": ("netlify",),
        "wrangler.toml": ("cloudflare",),
        "deno.json": ("deno",),
        "deno.jsonc": ("deno",),
        "app.yaml": ("gcloud",),
        "Dockerfile": ("fly", "railway"),
        "Procfile": ("heroku",),
    }

    @classmethod
    def detect_available(cls, project_path: str | None = None) -> list[dict[str, Any]]:
        """CLI tools present on PATH (``project_path`` reserved for future scoring)."""
        _ = project_path
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key in cls.PRIORITY:
            if key not in cls.CLI_REGISTRY:
                continue
            cfg = dict(cls.CLI_REGISTRY[key])
            if cfg.get("manual_only"):
                continue
            cfg["name"] = key
            bin_name = str(cfg.get("binary") or "")
            if not bin_name or bin_name in seen:
                continue
            if shutil.which(bin_name):
                seen.add(key)
                out.append(cfg)
        return out

    @classmethod
    def detect_by_file(cls, project_path: str) -> list[dict[str, Any]]:
        """Infer providers from config files (``vercel.json``, ``fly.toml``, …)."""
        path = Path(project_path)
        if not path.is_dir():
            return []

        found: list[dict[str, Any]] = []
        seen: set[str] = set()
        for fname, provider_keys in cls.FILE_HINTS.items():
            if not (path / fname).is_file():
                continue
            for pk in provider_keys:
                if pk in seen or pk not in cls.CLI_REGISTRY:
                    continue
                cfg = dict(cls.CLI_REGISTRY[pk])
                if cfg.get("manual_only"):
                    continue
                cfg["name"] = pk
                cfg["detected_by"] = f"config file: {fname}"
                bin_name = str(cfg.get("binary") or "")
                if bin_name and shutil.which(bin_name):
                    seen.add(pk)
                    found.append(cfg)
        return found

    @classmethod
    def detect_by_config_files(cls, project_path: str) -> list[dict[str, Any]]:
        """Alias for :meth:`detect_by_file` (compatible naming)."""
        return cls.detect_by_file(project_path)

    @classmethod
    def detect_by_framework(cls, project_path: str) -> list[dict[str, Any]]:
        """Hint Vercel when Next.js appears in ``package.json``."""
        path = Path(project_path)
        if not path.is_dir():
            return []
        pkg_path = path / "package.json"
        if not pkg_path.is_file():
            return []
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return []
        deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
        if "next" not in deps:
            return []
        key = "vercel"
        if key not in cls.CLI_REGISTRY:
            return []
        cfg = dict(cls.CLI_REGISTRY[key])
        if cfg.get("manual_only"):
            return []
        cfg["name"] = key
        cfg["detected_by"] = "framework: Next.js in package.json"
        bin_name = str(cfg.get("binary") or "")
        if not bin_name or not shutil.which(bin_name):
            return []
        return [cfg]

    @classmethod
    def get_registry(cls, provider: str) -> dict[str, Any] | None:
        """Normalize provider slug and return a registry entry."""
        key = _normalize_provider(provider)
        if not key or key not in cls.CLI_REGISTRY:
            return None
        cfg = dict(cls.CLI_REGISTRY[key])
        cfg["name"] = key
        return cfg


def _normalize_provider(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip().lower()
    aliases = {
        "google": "gcloud",
        "gcp": "gcloud",
        "flyctl": "fly",
        "fly.io": "fly",
        "aws-cli": "aws",
        "serverless": "aws",
        "wrangler": "cloudflare",
        "pages": "cloudflare",
        "workers": "cloudflare",
        "cloudflare-workers": "cloudflare",
        "cloudflare-pages": "cloudflare",
    }
    return aliases.get(s, s)
