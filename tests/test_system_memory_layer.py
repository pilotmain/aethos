from __future__ import annotations

import re

import pytest

from app.services import system_memory_files as smf
from app.services.general_answer_service import answer_general_question
from app.services.telegram_memory_commands import (
    format_memory_help,
    handle_memory_command,
    handle_memory_add,
    normalize_memory_command_text,
)


@pytest.fixture
def mem_root(tmp_path, monkeypatch):
    monkeypatch.setattr(smf, "project_root", lambda: tmp_path)
    return tmp_path


def test_ensure_system_memory_files_creates_soul_and_memory(mem_root) -> None:
    smf.ensure_system_memory_files()
    assert (mem_root / "soul.md").is_file()
    assert (mem_root / "memory.md").is_file()


def test_default_soul_includes_nexa_identity_and_creator(mem_root) -> None:
    smf.ensure_system_memory_files()
    soul = (mem_root / "soul.md").read_text(encoding="utf-8")
    assert "Nexa Soul" in soul or "Nexa" in soul
    assert "## Creator" in soul
    assert "Raya Ameha Meresa" in soul


def test_ensure_soul_creator_section_appends_once(mem_root) -> None:
    (mem_root / "soul.md").write_text("# Custom\n\nNo creator here.\n", encoding="utf-8")
    smf.ensure_soul_creator_section()
    text = (mem_root / "soul.md").read_text(encoding="utf-8")
    assert text.count("## Creator") == 1
    assert "Raya Ameha Meresa" in text


def test_ensure_soul_creator_section_idempotent(mem_root) -> None:
    smf.ensure_system_memory_files()
    smf.ensure_soul_creator_section()
    text = (mem_root / "soul.md").read_text(encoding="utf-8")
    assert text.count("## Creator") == 1


def test_append_memory_entry_writes_timestamped_block(mem_root) -> None:
    smf.ensure_system_memory_files()
    smf.append_memory_entry("Prefers concise answers.", source="test")
    mem = (mem_root / "memory.md").read_text(encoding="utf-8")
    assert "Prefers concise answers." in mem
    assert " — test" in mem


def test_append_memory_entry_rejects_secret_like(mem_root) -> None:
    smf.ensure_system_memory_files()
    with pytest.raises(ValueError, match="secret"):
        smf.append_memory_entry("my api_key is 123")


def test_read_system_memory_snapshot_returns_both(mem_root) -> None:
    smf.ensure_system_memory_files()
    snap = smf.read_system_memory_snapshot(max_chars_each=10_000)
    assert "Nexa" in snap.soul
    assert "Memories" in snap.memory or "memory" in snap.memory.lower()


def test_memory_command_help_and_soul_and_reload(mem_root) -> None:
    smf.ensure_system_memory_files()
    assert "soul.md" in format_memory_help()
    assert "Raya" in handle_memory_command("/memory soul")
    assert "no reload" in handle_memory_command("/memory reload").lower()


def test_memory_add_writes_and_secret_rejected(mem_root) -> None:
    smf.ensure_system_memory_files()
    assert "Added" in handle_memory_add("/memory add User prefers short answers.")
    mem = (mem_root / "memory.md").read_text(encoding="utf-8")
    assert "User prefers short answers." in mem
    assert "won’t store" in handle_memory_add("/memory add sk-deadbeef")


def test_normalize_memory_command_text() -> None:
    assert normalize_memory_command_text("/memory@NexaBot soul") == "/memory soul"


def test_build_system_prompt_includes_memory_block(mem_root, monkeypatch) -> None:
    from app.services.response_composer import ResponseContext, _build_system_prompt

    smf.ensure_system_memory_files()
    (mem_root / "soul.md").write_text(
        "# Nexa Soul\n\nCreator: Raya Ameha Meresa\n", encoding="utf-8"
    )

    def _root():
        return mem_root

    monkeypatch.setattr(smf, "project_root", _root)
    monkeypatch.setattr(
        "app.services.safe_llm_gateway.read_safe_system_memory_snapshot",
        smf.read_system_memory_snapshot,
    )

    ctx = ResponseContext(
        user_message="hi",
        intent="general_chat",
        behavior="clarify",
        has_active_plan=False,
        focus_task=None,
        selected_tasks=[],
        deferred_lines=[],
        planning_style="gentle",
        detected_state=None,
        voice_style="calm",
    )
    prompt = _build_system_prompt(ctx, "Strategy here.")
    assert "<soul.md>" in prompt
    assert "<memory.md>" in prompt
    assert "Raya Ameha Meresa" in prompt


def test_general_answer_system_includes_memory_block(mem_root, monkeypatch) -> None:
    smf.ensure_system_memory_files()
    (mem_root / "soul.md").write_text(
        "## Creator\n\nName: Raya Ameha Meresa\n", encoding="utf-8"
    )

    monkeypatch.setattr(smf, "project_root", lambda: mem_root)
    monkeypatch.setattr(
        "app.services.safe_llm_gateway.read_safe_system_memory_snapshot",
        smf.read_system_memory_snapshot,
    )

    captured: dict[str, str] = {}

    def _fake_safe(*, system_prompt: str, user_request: str, extra_text=None):
        captured["system"] = system_prompt
        _ = user_request
        _ = extra_text
        return "stubbed"

    monkeypatch.setattr(
        "app.services.general_answer_service.safe_llm_text_call",
        _fake_safe,
    )

    out = answer_general_question("Who created Nexa?")
    assert out == "stubbed"
    assert "Persistent Nexa context" in captured["system"]
    assert "Raya Ameha Meresa" in captured["system"]
