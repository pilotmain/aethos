# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""ClawHub marketplace CLI (Phase 17) — ``nexa clawhub …``."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any


def clawhub_dispatch(args: argparse.Namespace) -> int:
    ccmd = args.clawhub_cmd

    async def _search() -> int:
        from app.services.skills.clawhub_client import ClawHubClient

        client = ClawHubClient()
        q = str(getattr(args, "query", "") or "")
        lim = int(getattr(args, "limit", 20) or 20)
        rows = await client.search_skills(q, lim)
        if not rows:
            print("No skills found.")
            return 0
        for sk in rows:
            desc = (sk.description or "")[:72]
            print(f"  {sk.name} v{sk.version} — {desc}")
        return 0

    async def _popular() -> int:
        from app.services.skills.clawhub_client import ClawHubClient

        client = ClawHubClient()
        rows = await client.list_popular(20)
        for sk in rows:
            print(f"  {sk.name} v{sk.version} — ★ {sk.rating} ({sk.downloads} dl)")
        return 0

    async def _install() -> int:
        from app.services.skills.installer import SkillInstaller

        inst = SkillInstaller()
        force = bool(getattr(args, "force", False))
        ok, msg, key = await inst.install(str(args.name), str(args.version or "latest"), force=force)
        if ok:
            print(f"Installed {key} ({msg})")
            return 0
        print(f"Install failed: {msg}", file=sys.stderr)
        return 1

    async def _uninstall() -> int:
        from app.services.skills.installer import SkillInstaller

        ok, msg = await SkillInstaller().uninstall(str(args.name))
        if ok:
            print(f"Uninstalled {args.name}")
            return 0
        print(msg, file=sys.stderr)
        return 1

    async def _update() -> int:
        from app.services.skills.installer import SkillInstaller

        ok, msg = await SkillInstaller().update(str(args.name), force=bool(getattr(args, "force", False)))
        if ok:
            print(f"Update: {msg}")
            return 0
        print(msg, file=sys.stderr)
        return 1

    def _list_installed() -> int:
        from app.services.skills.installer import SkillInstaller

        skills = SkillInstaller().list_installed()
        if not skills:
            print("(no ClawHub-installed skills recorded)")
            return 0
        for s in skills:
            print(f"  {s.name} v{s.version} ({s.source.value}) — {s.status.value}")
        return 0

    if ccmd == "search":
        return asyncio.run(_search())
    if ccmd == "popular":
        return asyncio.run(_popular())
    if ccmd == "install":
        return asyncio.run(_install())
    if ccmd == "uninstall":
        return asyncio.run(_uninstall())
    if ccmd == "update":
        return asyncio.run(_update())
    if ccmd == "list-installed":
        return _list_installed()
    print("unknown clawhub subcommand", file=sys.stderr)
    return 2


def register_clawhub_parser(sub: Any) -> None:
    sp_ch = sub.add_parser("clawhub", help="ClawHub marketplace (Phase 17)")
    chs = sp_ch.add_subparsers(dest="clawhub_cmd", required=True)

    chs.add_parser("popular", help="List popular skills")
    sq = chs.add_parser("search", help="Search registry")
    sq.add_argument("query")
    sq.add_argument("--limit", type=int, default=20)

    chs.add_parser("list-installed", help="List installed marketplace skills")

    ib = chs.add_parser("install", help="Install a skill package")
    ib.add_argument("name")
    ib.add_argument("--version", default="latest")
    ib.add_argument(
        "--force",
        action="store_true",
        help="Bypass NEXA_CLAWHUB_REQUIRE_INSTALL_APPROVAL when set",
    )

    ub = chs.add_parser("uninstall", help="Remove installed skill")
    ub.add_argument("name")

    ub2 = chs.add_parser("update", help="Update installed skill")
    ub2.add_argument("name")
    ub2.add_argument("--force", action="store_true")


__all__ = ["clawhub_dispatch", "register_clawhub_parser"]
