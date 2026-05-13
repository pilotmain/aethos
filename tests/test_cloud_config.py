# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.deployment.cloud_config import CloudConfig
from app.services.deployment.generic_deploy import deploy_from_yaml_spec, render_template


def test_render_template() -> None:
    assert render_template("hello {project}", {"project": "x"}) == "hello x"


def test_cloud_config_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "clouds.yaml"
    cc = CloudConfig(config_path=p)
    cc.ensure_default()
    assert p.is_file()
    names = cc.list_providers()
    assert "vercel" in names
    assert "railway" in names
    cc.add_provider("custom", {"name": "Custom", "deploy_cmd": "echo ok"})
    cc.invalidate()
    assert cc.get_provider("custom") is not None
    assert cc.remove_provider("custom") is True


def test_deploy_from_yaml_spec_requires(tmp_path: Path) -> None:
    spec = {
        "deploy_cmd": "echo {bucket}",
        "requires": ["bucket"],
    }
    r = deploy_from_yaml_spec(
        provider_slug="aws_s3",
        spec=spec,
        project_path=str(tmp_path),
        preview=False,
        timeout_seconds=30.0,
        context=None,
    )
    assert r["success"] is False
    assert "Missing required context" in str(r.get("error", ""))


def test_deploy_from_yaml_spec_echo(tmp_path: Path) -> None:
    spec = {"deploy_cmd": "echo deploy_ok"}
    r = deploy_from_yaml_spec(
        provider_slug="test",
        spec=spec,
        project_path=str(tmp_path),
        preview=False,
        timeout_seconds=30.0,
    )
    assert r.get("success") is True
    assert "deploy_ok" in (r.get("stdout") or "")
