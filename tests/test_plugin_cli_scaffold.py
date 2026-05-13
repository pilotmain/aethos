# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.cli.plugin import scaffold_plugin_package, slugify_plugin_name


def test_slugify_plugin_name() -> None:
    assert slugify_plugin_name("My Cool Plugin!") == "my-cool-plugin"
    assert slugify_plugin_name("!!!") == "my-plugin"


def test_scaffold_plugin_package_writes_manifests(tmp_path: Path) -> None:
    d = tmp_path / "out"
    scaffold_plugin_package(d, "Demo Plugin")
    assert (d / "plugin.json").is_file()
    assert (d / "skill.yaml").is_file()
    assert (d / "handler.py").is_file()
    pj = json.loads((d / "plugin.json").read_text(encoding="utf-8"))
    assert pj["name"] == "demo-plugin"
    assert pj["tools"][0]["name"] == "echo"
    sk = yaml.safe_load((d / "skill.yaml").read_text(encoding="utf-8"))
    assert sk["name"] == "demo-plugin"
    assert sk["execution"]["handler"] == "run"
