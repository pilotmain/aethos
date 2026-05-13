# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Load cloud deploy definitions from ``clouds.yaml`` (user-extensible; no code changes per provider)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_cloud_singleton: CloudConfig | None = None


def _default_config_path() -> Path:
    try:
        from app.core.config import get_settings

        raw = str(getattr(get_settings(), "nexa_cloud_config_path", "") or "").strip()
        if raw:
            return Path(raw).expanduser()
    except Exception:
        pass
    env = (os.environ.get("NEXA_CLOUD_CONFIG_PATH") or "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".aethos" / "clouds.yaml"


DEFAULT_CLOUDS_YAML = """# AethOS cloud providers — edit or add entries; gateway uses ``deploy to <slug>``.
# Secrets in env values: ``{{ secrets.ENV_NAME }}`` reads from the process environment.
#
version: 1
default_provider: vercel

providers:
  vercel:
    name: "Vercel"
    deploy_cmd: "vercel --prod --yes"
    deploy_cmd_preview: "vercel --yes"
    login_cmd: "vercel login"
    login_probe: "vercel whoami"
    pre_deploy: "npm run build"
    env:
      VERCEL_TOKEN: "{{ secrets.VERCEL_TOKEN }}"
    url_pattern: |-
      https://[^\\s"']+\\.vercel\\.app[^\\s"']*

  railway:
    name: "Railway"
    deploy_cmd: "railway up"
    deploy_cmd_preview: "railway up"
    login_cmd: "railway login"
    login_probe: "railway whoami"
    env:
      RAILWAY_TOKEN: "{{ secrets.RAILWAY_TOKEN }}"
    url_pattern: |-
      https://[^\\s"']+\\.(?:up\\.railway\\.app|railway\\.app)[^\\s"']*

  netlify:
    name: "Netlify"
    deploy_cmd: "netlify deploy --prod"
    deploy_cmd_preview: "netlify deploy"
    login_cmd: "netlify login"
    login_probe: "netlify status"
    pre_deploy: "npm run build"
    url_pattern: |-
      https://[^\\s"']+\\.netlify\\.app[^\\s"']*

  cloudflare:
    name: "Cloudflare Pages"
    deploy_cmd: "wrangler pages deploy ./dist --project-name={project}"
    deploy_cmd_preview: "wrangler deploy"
    login_cmd: "wrangler login"
    login_probe: "wrangler whoami"
    pre_deploy: "npm run build"
    url_pattern: |-
      https://[^\\s"']+\\.(?:pages\\.dev|workers\\.dev)[^\\s"']*

  aws_s3:
    name: "AWS S3 sync"
    deploy_cmd: "aws s3 sync ./dist s3://{bucket} --delete"
    pre_deploy: "npm run build"
    login_cmd: "aws configure"
    login_probe: "aws sts get-caller-identity"
    env:
      AWS_ACCESS_KEY_ID: "{{ secrets.AWS_ACCESS_KEY_ID }}"
      AWS_SECRET_ACCESS_KEY: "{{ secrets.AWS_SECRET_ACCESS_KEY }}"
    url_pattern: "https://{bucket}.s3.amazonaws.com"
    requires:
      - bucket
"""


class CloudConfig:
    """Load ``clouds.yaml`` and expose provider entries."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._path = config_path
        self._config: dict[str, Any] | None = None

    @property
    def config_path(self) -> Path:
        return self._path if self._path is not None else _default_config_path()

    def ensure_default(self) -> Path:
        """Create parent dir and default file if missing; return resolved path."""
        path = self.config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            path.write_text(DEFAULT_CLOUDS_YAML, encoding="utf-8")
        return path

    def load(self) -> dict[str, Any]:
        if self._config is not None:
            return self._config
        path = self.config_path
        if not path.is_file():
            self.ensure_default()
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            data = {}
        self._config = data
        return self._config

    def invalidate(self) -> None:
        self._config = None

    def providers_map(self) -> dict[str, dict[str, Any]]:
        cfg = self.load()
        prov = cfg.get("providers") or {}
        if not isinstance(prov, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for k, v in prov.items():
            if isinstance(k, str) and isinstance(v, dict):
                out[k.strip()] = v
        return out

    def list_providers(self) -> list[str]:
        return sorted(self.providers_map().keys())

    def get_provider(self, name: str) -> dict[str, Any] | None:
        if not name or not isinstance(name, str):
            return None
        p = self.providers_map().get(name.strip().lower())
        return dict(p) if isinstance(p, dict) else None

    def default_provider(self) -> str | None:
        cfg = self.load()
        d = str(cfg.get("default_provider") or "").strip()
        return d.lower() or None

    def save(self, data: dict[str, Any]) -> None:
        path = self.config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
        self._config = dict(data)

    def add_provider(self, name: str, spec: dict[str, Any]) -> None:
        full = dict(self.load())
        prov = dict(full.get("providers") or {})
        prov[name.strip().lower()] = spec
        full["providers"] = prov
        self.save(full)

    def remove_provider(self, name: str) -> bool:
        key = name.strip().lower()
        full = dict(self.load())
        prov = dict(full.get("providers") or {})
        if key not in prov:
            return False
        del prov[key]
        full["providers"] = prov
        self.save(full)
        return True


def get_cloud_config() -> CloudConfig:
    global _cloud_singleton
    if _cloud_singleton is None:
        _cloud_singleton = CloudConfig()
    return _cloud_singleton


def init_cloud_config_file() -> Path:
    """Setup / CLI: ensure ``~/.aethos/clouds.yaml`` exists with defaults."""
    return get_cloud_config().ensure_default()


__all__ = ["CloudConfig", "DEFAULT_CLOUDS_YAML", "get_cloud_config", "init_cloud_config_file"]
