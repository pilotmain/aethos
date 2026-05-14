# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

from app.core.setup_creds_file import read_setup_creds_merged_dict, write_setup_creds


def test_read_setup_creds_merged_prefers_dotenv(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AETHOS_SETUP_CREDS_DOTENV_MERGE", raising=False)
    fake_home = tmp_path / "nh"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.setenv("AETHOS_SETUP_CREDS_FILE", str(tmp_path / "creds.json"))
    write_setup_creds(api_base="http://127.0.0.1:8010", user_id="from_json", bearer_token="json_tok")
    rep = tmp_path / "repo.env"
    rep.write_text("NEXA_WEB_API_TOKEN=from_dotenv\n")
    monkeypatch.setattr("app.core.config.ENV_FILE_PATH", rep)
    d = read_setup_creds_merged_dict()
    assert d.get("user_id") == "from_json"
    assert d.get("bearer_token") == "from_dotenv"
    assert d.get("api_base") == "http://127.0.0.1:8010"
