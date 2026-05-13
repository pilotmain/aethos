# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""CLI: manage ``~/.aethos/clouds.yaml`` providers (``aethos cloud …``)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cloud_main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(_repo_root() / ".env")
    except Exception:
        pass
    try:
        from app.core.aethos_env import apply_aethos_env_aliases

        apply_aethos_env_aliases()
    except Exception:
        pass

    av = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(prog="aethos cloud", description="Manage clouds.yaml deploy providers")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List configured provider slugs")

    sp_add = sub.add_parser("add", help="Add or replace a provider entry")
    sp_add.add_argument("name", help="Slug, e.g. myvps")
    sp_add.add_argument("--deploy-cmd", required=True, help="Argv-safe deploy command (quoted if needed)")
    sp_add.add_argument("--pre-deploy", default=None)
    sp_add.add_argument("--login-cmd", default=None)
    sp_add.add_argument("--login-probe", default=None)
    sp_add.add_argument("--url-pattern", default=None)
    sp_add.add_argument("--deploy-cmd-preview", default=None)

    sp_rm = sub.add_parser("remove", help="Remove a provider by slug")
    sp_rm.add_argument("name")

    args = p.parse_args(av)

    from app.services.deployment.cloud_config import get_cloud_config

    cc = get_cloud_config()

    if args.cmd == "list":
        names = cc.list_providers()
        if not names:
            print("No providers in clouds.yaml (unexpected — run aethos setup or delete clouds.yaml to reset).")
            return 0
        print("Configured providers:")
        for n in names:
            print(f"  • {n}")
        return 0

    if args.cmd == "add":
        spec: dict = {"deploy_cmd": str(args.deploy_cmd).strip()}
        if args.pre_deploy:
            spec["pre_deploy"] = str(args.pre_deploy).strip()
        if args.login_cmd:
            spec["login_cmd"] = str(args.login_cmd).strip()
        if args.login_probe:
            spec["login_probe"] = str(args.login_probe).strip()
        if args.url_pattern:
            spec["url_pattern"] = str(args.url_pattern).strip()
        if args.deploy_cmd_preview:
            spec["deploy_cmd_preview"] = str(args.deploy_cmd_preview).strip()
        spec["name"] = str(args.name).replace("_", " ").title()
        cc.add_provider(str(args.name).strip().lower(), spec)
        cc.invalidate()
        print(f"✅ Saved provider {str(args.name).strip().lower()!r} to {cc.config_path}")
        return 0

    if args.cmd == "remove":
        ok = cc.remove_provider(str(args.name))
        cc.invalidate()
        if ok:
            print(f"Removed provider {str(args.name).strip().lower()!r}")
            return 0
        print(f"Provider {str(args.name)!r} not found", file=sys.stderr)
        return 1

    return 1


__all__ = ["cloud_main"]
