# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Marketplace **plugins/skills** CLI — bridges OpenClaw-style commands to Phase 17 ClawHub + Phase 6 skills.

Runtime installs are **skill packages** (``skill.yaml`` + Python handlers) under
:data:`NEXA_CLAWHUB_SKILL_ROOT` / the plugin skill registry. Mission Control uses
``GET/POST /api/v1/marketplace/*``; cron automation uses ``/api/v1/clawhub/*``.

This module adds a stable ``aethos plugin …`` surface without duplicating registry
logic — it delegates to :mod:`app.cli.clawhub` and :mod:`app.cli.skills`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


def _ns(**kwargs: Any) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def slugify_plugin_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s).strip("-")
    return s or "my-plugin"


def scaffold_plugin_package(dest_dir: Path, display_name: str) -> Path:
    """Create ``plugin.json`` + ``skill.yaml`` + ``handler.py`` under ``dest_dir``."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify_plugin_name(display_name)
    plugin_meta = {
        "name": slug,
        "version": "1.0.0",
        "author": "",
        "license": "MIT",
        "entry": "handler.py",
        "tools": [
            {
                "name": "echo",
                "description": "Echo a short message (starter tool).",
                "parameters": {
                    "type": "object",
                    "properties": {"msg": {"type": "string", "description": "Message to echo"}},
                },
            }
        ],
        "permissions": [],
        "pricing": {"free": True, "price_usd": 0.0},
    }
    (dest_dir / "plugin.json").write_text(json.dumps(plugin_meta, indent=2) + "\n", encoding="utf-8")

    skill_yaml = f"""name: {slug}
version: 1.0.0
description: {display_name} (scaffolded plugin skill)
author: local
tags: [plugin, scaffold]
input_schema: {{}}
output_schema: {{}}
execution:
  type: python
  entry: handler.py
  handler: run
dependencies: []
permissions: []
"""
    (dest_dir / "skill.yaml").write_text(skill_yaml, encoding="utf-8")

    handler = '''"""Starter handler — replace with your tool implementations."""


def run(msg: str = "") -> dict:
    """Registered as ``execution.handler`` in skill.yaml."""
    return {"echo": (msg or "").strip(), "plugin": __name__}
'''
    (dest_dir / "handler.py").write_text(handler, encoding="utf-8")
    return dest_dir


def _resolve_local_skill_uri(local: str) -> Path:
    p = Path(local).expanduser().resolve()
    if p.is_file() and p.suffix.lower() in (".yaml", ".yml"):
        return p
    if p.is_dir():
        for cand in ("skill.yaml", "skill.yml"):
            fp = p / cand
            if fp.is_file():
                return fp
        raise ValueError(f"No skill.yaml or skill.yml under {p}")
    raise ValueError(f"Not a skill manifest or directory: {local}")


def _skill_name_from_manifest(manifest: Path) -> str:
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "name" not in data:
        raise ValueError(f"Invalid skill manifest: {manifest}")
    return str(data["name"]).strip()


def plugin_dispatch(args: argparse.Namespace) -> int:
    from app.cli.clawhub import clawhub_dispatch
    from app.cli.skills import cmd_skills_install

    cmd = str(getattr(args, "plugin_cmd", "") or "")

    if cmd == "search":
        return clawhub_dispatch(
            _ns(clawhub_cmd="search", query=str(args.query), limit=int(args.limit or 20))
        )
    if cmd == "popular":
        return clawhub_dispatch(_ns(clawhub_cmd="popular"))
    if cmd == "list":
        return clawhub_dispatch(_ns(clawhub_cmd="list-installed"))
    if cmd == "install":
        local = getattr(args, "local", None)
        if local:
            try:
                manifest = _resolve_local_skill_uri(str(local))
            except ValueError as e:
                print(str(e), file=sys.stderr)
                return 1
            nm = (getattr(args, "name", None) or "").strip() or _skill_name_from_manifest(manifest)
            uri = f"file://{manifest}"
            return cmd_skills_install(nm, uri)
        name = (getattr(args, "name", None) or "").strip()
        if not name:
            print("install: pass SKILL_NAME or --local PATH", file=sys.stderr)
            return 2
        return clawhub_dispatch(
            _ns(
                clawhub_cmd="install",
                name=name,
                version=str(getattr(args, "version", "latest") or "latest"),
                force=bool(getattr(args, "force", False)),
            )
        )
    if cmd == "uninstall":
        return clawhub_dispatch(_ns(clawhub_cmd="uninstall", name=str(args.name)))
    if cmd == "update":
        if bool(getattr(args, "update_all", False)):

            async def _all() -> int:
                from app.services.skills.clawhub_models import SkillSource
                from app.services.skills.installer import SkillInstaller

                inst = SkillInstaller()
                rows = [r for r in inst.list_installed() if r.source == SkillSource.CLAWHUB]
                if not rows:
                    print("(no ClawHub-installed skills to update)")
                    return 0
                rc = 0
                force = bool(getattr(args, "force", False))
                for r in rows:
                    ok, msg = await inst.update(r.name, force=force)
                    tag = "ok" if ok else "fail"
                    print(f"  [{tag}] {r.name}: {msg}")
                    if not ok:
                        rc = 1
                return rc

            return asyncio.run(_all())
        nm = (getattr(args, "name", None) or "").strip()
        if not nm:
            print("update: pass SKILL_NAME or use --all", file=sys.stderr)
            return 2
        return clawhub_dispatch(
            _ns(
                clawhub_cmd="update",
                name=nm,
                force=bool(getattr(args, "force", False)),
            )
        )
    if cmd == "create":
        name = str(getattr(args, "name", "") or "").strip()
        if not name:
            print("create: NAME is required", file=sys.stderr)
            return 2
        out = getattr(args, "out", None)
        dest = Path(out).expanduser().resolve() if out else Path.cwd() / slugify_plugin_name(name)
        if dest.exists():
            if dest.is_file():
                print(f"refuse: {dest} is a file (expected a directory path)", file=sys.stderr)
                return 1
            if any(dest.iterdir()):
                print(f"refuse: directory not empty: {dest}", file=sys.stderr)
                return 1
        scaffold_plugin_package(dest, name)
        print(f"Scaffolded plugin skill at {dest}")
        print(f"  Install:  aethos plugin install --local {dest}")
        print("  Or:       aethos skills install <name-from-skill.yaml> file://" + str(dest / "skill.yaml"))
        return 0

    print("unknown plugin subcommand", file=sys.stderr)
    return 2


def register_plugin_parser(sub: Any) -> None:
    sp = sub.add_parser(
        "plugin",
        help="Marketplace skills/plugins (ClawHub + local skill.yaml; wraps clawhub + skills install)",
    )
    ch = sp.add_subparsers(dest="plugin_cmd", required=True)

    sq = ch.add_parser("search", help="Search ClawHub registry")
    sq.add_argument("query")
    sq.add_argument("--limit", type=int, default=20)

    ch.add_parser("popular", help="List popular skills on ClawHub")
    ch.add_parser("list", help="List installed marketplace (ClawHub) skills")

    ib = ch.add_parser("install", help="Install from ClawHub by name, or --local path to skill.yaml / skill dir")
    ib.add_argument("name", nargs="?", default=None, help="ClawHub skill name (omit when using --local)")
    ib.add_argument("--version", default="latest")
    ib.add_argument("--local", metavar="PATH", default=None, help="Directory with skill.yaml or path to manifest")
    ib.add_argument(
        "--force",
        action="store_true",
        help="Bypass NEXA_CLAWHUB_REQUIRE_INSTALL_APPROVAL for ClawHub installs",
    )

    ub = ch.add_parser("uninstall", help="Remove installed ClawHub skill")
    ub.add_argument("name")

    ub2 = ch.add_parser("update", help="Update one ClawHub skill, or all with --all")
    ub2.add_argument("name", nargs="?", default=None)
    ub2.add_argument("--all", action="store_true", dest="update_all", help="Update every ClawHub-installed skill")
    ub2.add_argument("--force", action="store_true")

    cr = ch.add_parser("create", help="Scaffold plugin.json + skill.yaml + handler.py in a new directory")
    cr.add_argument("name", help="Display or package name (slugified for paths)")
    cr.add_argument(
        "--out",
        dest="out",
        default=None,
        help="Output directory (default: ./<slug> under current working directory)",
    )


__all__ = ["plugin_dispatch", "register_plugin_parser", "scaffold_plugin_package", "slugify_plugin_name"]
