"""Agent harness plugins (Cursor, Claude Code, Codex, OpenCode, Continue)."""

from secret_broker.harness.base import HarnessPlugin, InstallResult, Scope
from secret_broker.harness.registry import get_plugin, list_plugins

__all__ = [
    "HarnessPlugin",
    "InstallResult",
    "Scope",
    "get_plugin",
    "list_plugins",
]
