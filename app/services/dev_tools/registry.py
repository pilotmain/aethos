from __future__ import annotations

from app.services.dev_tools.aider_connector import AiderConnector
from app.services.dev_tools.base import DevToolConnector
from app.services.dev_tools.ide_connectors import (
    AndroidStudioConnector,
    CursorConnector,
    IntelliJConnector,
    ManualConnector,
    PyCharmConnector,
    VSCodeConnector,
    WebStormConnector,
    XcodeConnector,
)

CONNECTORS: dict[str, DevToolConnector] = {
    "aider": AiderConnector(),
    "cursor": CursorConnector(),
    "vscode": VSCodeConnector(),
    "intellij": IntelliJConnector(),
    "pycharm": PyCharmConnector(),
    "webstorm": WebStormConnector(),
    "android_studio": AndroidStudioConnector(),
    "xcode": XcodeConnector(),
    "manual": ManualConnector(),
}


def get_dev_tool(key: str) -> DevToolConnector | None:
    if not key:
        return None
    return CONNECTORS.get(key.strip().lower())


def list_dev_tools() -> list[DevToolConnector]:
    return list(CONNECTORS.values())
