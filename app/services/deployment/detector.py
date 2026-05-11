"""Detect installed deployment CLIs and infer hints from project files."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


class DeploymentDetector:
    """
    Known CLIs — binaries checked with :func:`shutil.which`.

    Deploy commands are argv lists (no shell) except where ``deploy_shell`` is set for legacy flows.
    """

    #: Priority order for auto-deploy when multiple CLIs match (first wins in executor).
    PRIORITY: tuple[str, ...] = (
        "vercel",
        "railway",
        "fly",
        "netlify",
        "gcloud",
    )

    CLI_REGISTRY: dict[str, dict[str, Any]] = {
        "vercel": {
            "binary": "vercel",
            "deploy_argv": ["vercel", "--prod", "--yes"],
            "login_hint": "vercel login",
            "url_pattern": r"https://[^\s\"']+\.vercel\.app[^\s\"']*",
        },
        "railway": {
            "binary": "railway",
            "deploy_argv": ["railway", "up"],
            "login_hint": "railway login",
            "url_pattern": r"https://[^\s\"']+\.(?:up\.railway\.app|railway\.app)[^\s\"']*",
        },
        "aws": {
            "binary": "aws",
            "manual_only": True,
            "login_hint": "aws configure",
            "url_pattern": r"https://[^\s\"']+\.amazonaws\.com[^\s\"']*",
            "note": "No single generic AWS deploy; use SAM/CDK/ECS/your pipeline.",
        },
        "gcloud": {
            "binary": "gcloud",
            "deploy_argv": ["gcloud", "app", "deploy", "--quiet"],
            "login_hint": "gcloud auth login",
            "url_pattern": r"https://[^\s\"']+\.appspot\.com[^\s\"']*",
            "note": "Requires app.yaml in project for App Engine deploy.",
        },
        "fly": {
            "binary": "flyctl",
            "deploy_argv": ["flyctl", "deploy"],
            "login_hint": "flyctl auth login",
            "url_pattern": r"https://[^\s\"']+\.fly\.dev[^\s\"']*",
        },
        "netlify": {
            "binary": "netlify",
            "deploy_argv": ["netlify", "deploy", "--prod"],
            "login_hint": "netlify login",
            "url_pattern": r"https://[^\s\"']+\.netlify\.app[^\s\"']*",
        },
        "heroku": {
            "binary": "heroku",
            "deploy_shell": "git push heroku HEAD:main",
            "login_hint": "heroku login",
            "url_pattern": r"https://[^\s\"']+\.herokuapp\.com[^\s\"']*",
            "note": "Requires git remote `heroku`; uses shell.",
            "shell_unsafe": True,
        },
    }

    FILE_HINTS: dict[str, tuple[str, ...]] = {
        "vercel.json": ("vercel",),
        "vercel.toml": ("vercel",),
        "railway.json": ("railway",),
        "railway.toml": ("railway",),
        "fly.toml": ("fly",),
        "netlify.toml": ("netlify",),
        "app.yaml": ("gcloud",),
        "Dockerfile": ("fly", "railway"),
    }

    @classmethod
    def detect_available(cls) -> list[dict[str, Any]]:
        """Return registry entries for CLIs whose binary exists on PATH."""
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
        """Prefer providers suggested by project metadata files."""
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
                bin_name = str(cfg.get("binary") or "")
                if bin_name and shutil.which(bin_name):
                    seen.add(pk)
                    found.append(cfg)
        return found

    @classmethod
    def get_registry(cls, provider: str) -> dict[str, Any] | None:
        """Normalize provider slug (``vercel``, ``google`` → ``gcloud``, ``flyctl`` → ``fly``)."""
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
    }
    return aliases.get(s, s)
