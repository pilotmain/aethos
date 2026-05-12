"""Gateway NL development task routing and workspace patches."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.gateway.context import GatewayContext
from app.services.gateway.development_nl import try_development_nl_gateway_turn


_MIN_APP_JS = """const form = document.getElementById("add-form");
const input = document.getElementById("task");
const list = document.getElementById("list");
let items = [];
function render() {
  list.innerHTML = "";
  items.forEach((text, i) => {
    const li = document.createElement("li");
    const originalIndex = i;
    const completeBtn = document.createElement("button");
    completeBtn.textContent = "Done";
    li.appendChild(completeBtn);
    const main = document.createElement("span");
    main.textContent = String(text);
    li.appendChild(main);
    list.appendChild(li);
  });
}
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const v = input.value.trim();
  if (!v) return;
  items.push(v);
  input.value = "";
  render();
});
"""


def test_development_nl_add_delete_button(tmp_path: Path) -> None:
    proj = tmp_path / "my-todo-demo"
    proj.mkdir()
    (proj / "index.html").write_text('<form id="add-form"><input id="task"/></form><ul id="list"></ul>', encoding="utf-8")
    (proj / "app.js").write_text(_MIN_APP_JS, encoding="utf-8")
    (proj / "styles.css").write_text("body { margin: 0; }\n", encoding="utf-8")

    gctx = GatewayContext(user_id="tg_owner")

    with (
        patch(
            "app.services.gateway.development_nl._workspace_root_for_nl",
            return_value=str(tmp_path),
        ),
        patch(
            "app.services.gateway.development_nl.is_privileged_owner_for_web_mutations",
            return_value=True,
        ),
        patch("app.services.gateway.development_nl.get_settings") as gs,
    ):
        gs.return_value = MagicMock(nexa_auto_approve_owner=True)
        out = try_development_nl_gateway_turn(
            gctx,
            "Development add a delete button to the todo app",
            MagicMock(),
        )
    assert out is not None
    assert out.get("mode") == "chat"
    assert out.get("intent") == "development_nl_done"
    patched = (proj / "app.js").read_text(encoding="utf-8")
    assert "delete-btn" in patched
    assert ".delete-btn" in (proj / "styles.css").read_text(encoding="utf-8")


def test_development_nl_non_owner_returns_none(tmp_path: Path) -> None:
    gctx = GatewayContext(user_id="other")
    with (
        patch(
            "app.services.gateway.development_nl._workspace_root_for_nl",
            return_value=str(tmp_path),
        ),
        patch(
            "app.services.gateway.development_nl.is_privileged_owner_for_web_mutations",
            return_value=False,
        ),
        patch("app.services.gateway.development_nl.get_settings") as gs,
    ):
        gs.return_value = MagicMock(nexa_auto_approve_owner=True)
        assert (
            try_development_nl_gateway_turn(
                gctx,
                "Development add a delete button to the todo app",
                MagicMock(),
            )
            is None
        )


def test_development_nl_no_todo_project(tmp_path: Path) -> None:
    gctx = GatewayContext(user_id="tg_owner")
    with (
        patch(
            "app.services.gateway.development_nl._workspace_root_for_nl",
            return_value=str(tmp_path),
        ),
        patch(
            "app.services.gateway.development_nl.is_privileged_owner_for_web_mutations",
            return_value=True,
        ),
        patch("app.services.gateway.development_nl.get_settings") as gs,
    ):
        gs.return_value = MagicMock(nexa_auto_approve_owner=True)
        out = try_development_nl_gateway_turn(
            gctx,
            "Development add a delete button to the todo app",
            MagicMock(),
        )
    assert out is not None
    assert out.get("intent") == "development_nl_error"
    assert "todo" in (out.get("text") or "").lower()


def test_development_nl_vague_task_handoff(tmp_path: Path) -> None:
    proj = tmp_path / "x-todo-y"
    proj.mkdir()
    (proj / "index.html").write_text("<html/>", encoding="utf-8")
    (proj / "app.js").write_text(_MIN_APP_JS, encoding="utf-8")
    (proj / "styles.css").write_text("", encoding="utf-8")

    gctx = GatewayContext(user_id="tg_owner")
    with (
        patch(
            "app.services.gateway.development_nl._workspace_root_for_nl",
            return_value=str(tmp_path),
        ),
        patch(
            "app.services.gateway.development_nl.is_privileged_owner_for_web_mutations",
            return_value=True,
        ),
        patch("app.services.gateway.development_nl.get_settings") as gs,
    ):
        gs.return_value = MagicMock(nexa_auto_approve_owner=True)
        out = try_development_nl_gateway_turn(
            gctx,
            "Development refactor the entire architecture",
            MagicMock(),
        )
    assert out is not None
    assert out.get("intent") == "development_nl_handoff"
    assert "/subagent list" in (out.get("text") or "")
