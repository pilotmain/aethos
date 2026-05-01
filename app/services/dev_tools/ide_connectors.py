from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.services.dev_tools.base import DevToolConnector, DevToolResult


def _mac_open_app(app_name: str, repo_path: Path) -> DevToolResult:
    result = subprocess.run(  # noqa: S603
        ["open", "-a", app_name, str(repo_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    ok = result.returncode == 0
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()

    return DevToolResult(
        ok=ok,
        message=f"Opened {repo_path} in {app_name}." if ok else f"Could not open {app_name}.",
        details=output or None,
    )


def _cli_open(binary: str, repo_path: Path) -> DevToolResult:
    found = shutil.which(binary)

    if not found:
        return DevToolResult(
            ok=False,
            message=f"{binary} command is not available on PATH.",
        )

    result = subprocess.run(  # noqa: S603
        [found, str(repo_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    ok = result.returncode == 0
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()

    return DevToolResult(
        ok=ok,
        message=f"Opened {repo_path} with {binary}." if ok else f"Could not open {binary}.",
        details=output or None,
    )


class CursorConnector(DevToolConnector):
    key = "cursor"
    display_name = "Cursor"
    supported_modes = ["ide_handoff"]

    def is_available(self) -> bool:
        return shutil.which("cursor") is not None

    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        if shutil.which("cursor"):
            return _cli_open("cursor", repo_path)
        return _mac_open_app("Cursor", repo_path)


class VSCodeConnector(DevToolConnector):
    key = "vscode"
    display_name = "VS Code"
    supported_modes = ["ide_handoff"]

    def is_available(self) -> bool:
        return shutil.which("code") is not None

    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        return _cli_open("code", repo_path)


class IntelliJConnector(DevToolConnector):
    key = "intellij"
    display_name = "IntelliJ IDEA"
    supported_modes = ["ide_handoff"]

    def is_available(self) -> bool:
        return True

    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        return _mac_open_app("IntelliJ IDEA", repo_path)


class PyCharmConnector(DevToolConnector):
    key = "pycharm"
    display_name = "PyCharm"
    supported_modes = ["ide_handoff"]

    def is_available(self) -> bool:
        return True

    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        return _mac_open_app("PyCharm", repo_path)


class WebStormConnector(DevToolConnector):
    key = "webstorm"
    display_name = "WebStorm"
    supported_modes = ["ide_handoff"]

    def is_available(self) -> bool:
        return True

    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        return _mac_open_app("WebStorm", repo_path)


class AndroidStudioConnector(DevToolConnector):
    key = "android_studio"
    display_name = "Android Studio"
    supported_modes = ["ide_handoff"]

    def is_available(self) -> bool:
        return True

    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        return _mac_open_app("Android Studio", repo_path)


class XcodeConnector(DevToolConnector):
    key = "xcode"
    display_name = "Xcode"
    supported_modes = ["ide_handoff"]

    def is_available(self) -> bool:
        return True

    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        return _mac_open_app("Xcode", repo_path)


class ManualConnector(DevToolConnector):
    key = "manual"
    display_name = "Manual"
    supported_modes = ["manual_review"]

    def is_available(self) -> bool:
        return True

    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        return DevToolResult(
            ok=True,
            message=f"Manual handoff prepared for {repo_path}.",
            details=f"Task file: {task_file}" if task_file else None,
        )
