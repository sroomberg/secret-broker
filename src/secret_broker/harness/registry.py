"""Harness plugin registry."""

from __future__ import annotations

from secret_broker.harness.base import HarnessPlugin
from secret_broker.harness.claude_code import ClaudeCodePlugin
from secret_broker.harness.codex import CodexPlugin
from secret_broker.harness.continue_ide import ContinuePlugin
from secret_broker.harness.cursor import CursorPlugin
from secret_broker.harness.opencode import OpenCodePlugin

_PLUGINS: list[HarnessPlugin] = [
    CursorPlugin(),
    ClaudeCodePlugin(),
    CodexPlugin(),
    OpenCodePlugin(),
    ContinuePlugin(),
]


def list_plugins() -> list[HarnessPlugin]:
    return list(_PLUGINS)


def get_plugin(harness_id: str) -> HarnessPlugin:
    for plugin in _PLUGINS:
        if plugin.id == harness_id:
            return plugin
    raise KeyError(harness_id)
