"""OpenCode harness — ~/.config/opencode/opencode.json or ./opencode.json."""

from __future__ import annotations

from pathlib import Path

from secret_broker.harness.base import (
    SERVER_NAME,
    HarnessPlugin,
    HarnessStatus,
    InstallResult,
    Scope,
)
from secret_broker.harness.common import (
    json_has_server,
    mcp_stdio_entry,
    merge_mcp_servers_json,
    remove_mcp_server_json,
)


class OpenCodePlugin(HarnessPlugin):
    id = "opencode"
    name = "OpenCode"
    supports_mcp = True
    supports_hooks = False

    def _path(self, *, scope: Scope, root: Path, home: Path) -> Path:
        if scope == Scope.USER:
            return home / ".config" / "opencode" / "opencode.json"
        return root / "opencode.json"

    def status(self, *, scope: Scope, root: Path, home: Path) -> HarnessStatus:
        path = self._path(scope=scope, root=root, home=home)
        ok = json_has_server(path, key="mcp")
        return HarnessStatus(
            harness=self.id,
            installed=ok,
            scope=scope,
            mcp=ok,
            paths=[str(path)],
            detail="mcp present" if ok else "not installed",
        )

    def install(
        self,
        *,
        scope: Scope,
        root: Path,
        home: Path,
        broker_command: list[str],
        config_path: str | None,
        with_hooks: bool,
    ) -> InstallResult:
        path = self._path(scope=scope, root=root, home=home)
        entry = mcp_stdio_entry(broker_command, config_path=config_path, style="opencode")
        merge_mcp_servers_json(path, entry=entry, key="mcp", server_name=SERVER_NAME)
        return InstallResult(
            harness=self.id,
            scope=scope,
            paths_touched=[str(path)],
            mcp_installed=True,
            hooks_installed=False,
            detail="hooks not supported; MCP only" if with_hooks else "mcp installed",
        )

    def uninstall(self, *, scope: Scope, root: Path, home: Path) -> InstallResult:
        path = self._path(scope=scope, root=root, home=home)
        removed = remove_mcp_server_json(path, key="mcp", server_name=SERVER_NAME)
        return InstallResult(
            harness=self.id,
            scope=scope,
            paths_touched=[str(path)] if removed else [],
            detail="removed" if removed else "nothing to remove",
        )
