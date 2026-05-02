"""On-demand local file intent (paths relative to host work root)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.local_file_intent import infer_local_file_request


def test_infer_summarize_absolute_under_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "contracts"
    sub.mkdir()
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request(f"Summarize payment terms in {sub.resolve()}")
    assert lf.matched and lf.payload
    assert lf.payload.get("host_action") == "read_multiple_files"
    assert lf.payload.get("intel_analysis") is True


def test_infer_compare_two_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request("Compare a.txt and b.txt")
    assert lf.matched and lf.payload
    assert lf.payload.get("relative_paths") == ["a.txt", "b.txt"]
    assert lf.payload.get("intel_operation") == "compare"


def test_infer_find_keyword(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request('Find files mentioning pricing in .')
    assert lf.matched and lf.payload
    assert lf.payload.get("keyword") == "pricing"


def test_infer_list_files_absolute_without_in_keyword(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    outer = Path("/tmp/nexa_infer_list_abs_test_dir")
    outer.mkdir(parents=True, exist_ok=True)

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request(f"list files {outer}", default_relative_base=".")
    assert lf.matched and lf.payload
    assert lf.payload.get("nexa_permission_abs_targets") == [str(outer.resolve())]


def test_infer_list_files_outside_work_root_still_carries_abs_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    outer = tmp_path.parent / "nexa_intent_outer_list"
    outer.mkdir(exist_ok=True)

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request(f"list files in {outer}")
    assert lf.matched and lf.payload
    assert lf.payload.get("host_action") == "list_directory"
    assert lf.payload.get("nexa_permission_abs_targets") == [str(outer.resolve())]


def test_infer_read_local_file_asks_file_clarification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request("read a local file and summarize it")
    assert lf.matched
    assert lf.clarification_message
    assert "What file should I read?" in (lf.clarification_message or "")
    assert lf.clarification_axis == "file"
    assert "Which folder should I read?" not in (lf.clarification_message or "")
    assert lf.payload is None


def test_infer_read_files_generic_folder_asks_clarification_not_app_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request("read files in my local folder")
    assert lf.matched
    assert lf.clarification_message
    assert "full path" in (lf.clarification_message or "").lower()
    assert "Which folder should I read?" in (lf.clarification_message or "")
    assert lf.clarification_axis == "folder"
    assert lf.payload is None


def test_infer_analyze_folder_outside_work_root_carries_abs_targets_and_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    outer = tmp_path.parent / "nexa_infer_analyze_outer"
    outer.mkdir(exist_ok=True)

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request(f"analyze folder {outer}")
    assert lf.matched and lf.payload
    assert lf.payload.get("host_action") == "read_multiple_files"
    assert lf.payload.get("nexa_permission_abs_targets") == [str(outer.resolve())]
    assert lf.payload.get("base") == str(outer.resolve())
    assert lf.payload.get("relative_path") == "."


def test_infer_infra_keywords_not_filesystem_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phrases like 'in EKS' / 'Spring' must not resolve as repo-relative folders (Phase 51+ routing)."""
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request(
            "Summarize my MongoDB Atlas + Spring Boot service deployed in EKS with custom OIDC"
        )
    assert not lf.matched


def test_infer_list_files_in_eks_not_path_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request("list files in eks")
    assert not lf.matched


def test_infer_https_only_defers_to_other_routing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request("check https://example.com/path for broken links")
    assert not lf.matched
