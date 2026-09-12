"""Claude Code harness — user ~/.claude.json mcpServers; project .mcp.json + hooks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from secret_broker.harness.assets import ensure_plugin_contract, materialize_mcp_entry
from secret_broker.harness.base import (
    HarnessPlugin,
    HarnessStatus,
    InstallResult,
    Scope,
)
from secret_broker.harness.common import (
    install_hook_script,
    json_has_server,
    merge_mcp_servers_json,
    read_json,
    remove_mcp_server_json,
    write_json,
)

HOOK_MARKER = "secret-broker/block_secret_read"


class ClaudeCodePlugin(HarnessPlugin):
    id = "claude-code"
    name = "Claude Code"
    supports_mcp = True
    supports_hooks = True

    def _mcp_path(self, *, scope: Scope, root: Path, home: Path) -> Path:
        if scope == Scope.USER:
            return home / ".claude.json"
        return root / ".mcp.json"

    def _settings_path(self, *, scope: Scope, root: Path, home: Path) -> Path:
        if scope == Scope.USER:
            return home / ".claude" / "settings.json"
        return root / ".claude" / "settings.json"

    def _hooks_dir(self, *, scope: Scope, root: Path, home: Path) -> Path:
        if scope == Scope.USER:
            return home / ".claude" / "hooks" / "secret-broker"
        return root / ".claude" / "hooks" / "secret-broker"

    def status(self, *, scope: Scope, root: Path, home: Path) -> HarnessStatus:
        mcp_path = self._mcp_path(scope=scope, root=root, home=home)
        settings = self._settings_path(scope=scope, root=root, home=home)
        mcp_ok = json_has_server(mcp_path)
        hooks_ok = self._hooks_present(settings)
        return HarnessStatus(
            harness=self.id,
            installed=mcp_ok or hooks_ok,
            scope=scope,
            mcp=mcp_ok,
            hooks=hooks_ok,
            paths=[str(mcp_path), str(settings)],
            detail=f"mcp={mcp_ok} hooks={hooks_ok}",
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
        ensure_plugin_contract(self.id)
        mcp_path = self._mcp_path(scope=scope, root=root, home=home)
        entry = materialize_mcp_entry(
            self.id,
            broker_command=broker_command,
            config_path=config_path,
            style="claude",
        )
        merge_mcp_servers_json(mcp_path, entry=entry)
        paths = [str(mcp_path)]
        hooks_installed = False
        if with_hooks:
            hooks_dir = self._hooks_dir(scope=scope, root=root, home=home)
            script = install_hook_script(hooks_dir)
            settings = self._settings_path(scope=scope, root=root, home=home)
            self._ensure_hooks(settings, script)
            paths.extend([str(script), str(settings)])
            hooks_installed = True
        return InstallResult(
            harness=self.id,
            scope=scope,
            paths_touched=paths,
            mcp_installed=True,
            hooks_installed=hooks_installed,
            detail="mcp+hooks" if hooks_installed else "mcp",
        )

    def uninstall(self, *, scope: Scope, root: Path, home: Path) -> InstallResult:
        mcp_path = self._mcp_path(scope=scope, root=root, home=home)
        removed = remove_mcp_server_json(mcp_path)
        settings = self._settings_path(scope=scope, root=root, home=home)
        self._remove_hooks(settings)
        return InstallResult(
            harness=self.id,
            scope=scope,
            paths_touched=[str(mcp_path), str(settings)],
            detail="removed" if removed else "cleaned hooks/mcp if present",
        )

    def _hooks_present(self, settings: Path) -> bool:
        if not settings.exists():
            return False
        return HOOK_MARKER in settings.read_text(encoding="utf-8")

    def _ensure_hooks(self, settings: Path, script: Path) -> None:
        data = read_json(settings)
        hooks = data.setdefault("hooks", {})
        pre = hooks.setdefault("PreToolUse", [])
        hooks["PreToolUse"] = [g for g in pre if HOOK_MARKER not in json.dumps(g)]
        command = f"{sys.executable} {script}"
        hooks["PreToolUse"].append(
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                        "timeout": 10,
                        "statusMessage": "secret-broker policy",
                    }
                ],
            }
        )
        data["_secret_broker_hook"] = HOOK_MARKER
        write_json(settings, data)

    def _remove_hooks(self, settings: Path) -> None:
        if not settings.exists():
            return
        data = read_json(settings)
        data.pop("_secret_broker_hook", None)
        hooks = data.get("hooks")
        if isinstance(hooks, dict) and "PreToolUse" in hooks:
            hooks["PreToolUse"] = [
                g
                for g in hooks["PreToolUse"]
                if HOOK_MARKER not in json.dumps(g) and "secret-broker" not in json.dumps(g)
            ]
            data["hooks"] = hooks
        write_json(settings, data)
