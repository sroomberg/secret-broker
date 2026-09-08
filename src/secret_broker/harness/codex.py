"""OpenAI Codex harness — ~/.codex/config.toml + optional hooks.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from secret_broker.harness.base import (
    HarnessPlugin,
    HarnessStatus,
    InstallResult,
    Scope,
)
from secret_broker.harness.common import (
    codex_has_server,
    install_hook_script,
    read_json,
    remove_codex_mcp,
    upsert_codex_mcp,
    write_json,
)

HOOK_MARKER = "secret-broker/block_secret_read"


class CodexPlugin(HarnessPlugin):
    id = "codex"
    name = "Codex"
    supports_mcp = True
    supports_hooks = True

    def _config_path(self, *, scope: Scope, root: Path, home: Path) -> Path:
        base = home / ".codex" if scope == Scope.USER else root / ".codex"
        return base / "config.toml"

    def _hooks_path(self, *, scope: Scope, root: Path, home: Path) -> Path:
        base = home / ".codex" if scope == Scope.USER else root / ".codex"
        return base / "hooks.json"

    def _hooks_dir(self, *, scope: Scope, root: Path, home: Path) -> Path:
        base = home / ".codex" if scope == Scope.USER else root / ".codex"
        return base / "hooks" / "secret-broker"

    def status(self, *, scope: Scope, root: Path, home: Path) -> HarnessStatus:
        cfg = self._config_path(scope=scope, root=root, home=home)
        hooks = self._hooks_path(scope=scope, root=root, home=home)
        mcp_ok = codex_has_server(cfg)
        hooks_ok = hooks.exists() and HOOK_MARKER in hooks.read_text(encoding="utf-8")
        return HarnessStatus(
            harness=self.id,
            installed=mcp_ok or hooks_ok,
            scope=scope,
            mcp=mcp_ok,
            hooks=hooks_ok,
            paths=[str(cfg), str(hooks)],
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
        cfg = self._config_path(scope=scope, root=root, home=home)
        upsert_codex_mcp(cfg, broker_command, config_path)
        # Ensure features.hooks can be enabled when hooks requested
        paths = [str(cfg)]
        hooks_installed = False
        if with_hooks:
            self._ensure_features_hooks(cfg)
            script = install_hook_script(self._hooks_dir(scope=scope, root=root, home=home))
            hooks_path = self._hooks_path(scope=scope, root=root, home=home)
            self._write_hooks(hooks_path, script)
            paths.extend([str(script), str(hooks_path)])
            hooks_installed = True
        return InstallResult(
            harness=self.id,
            scope=scope,
            paths_touched=paths,
            mcp_installed=True,
            hooks_installed=hooks_installed,
        )

    def uninstall(self, *, scope: Scope, root: Path, home: Path) -> InstallResult:
        cfg = self._config_path(scope=scope, root=root, home=home)
        removed = remove_codex_mcp(cfg)
        hooks_path = self._hooks_path(scope=scope, root=root, home=home)
        if hooks_path.exists():
            data = read_json(hooks_path)
            # Drop PreToolUse groups that reference secret-broker
            pre = data.get("PreToolUse") or data.get("hooks", {}).get("PreToolUse")
            if isinstance(pre, list):
                filtered = [g for g in pre if "secret-broker" not in json.dumps(g)]
                if "hooks" in data and isinstance(data["hooks"], dict):
                    data["hooks"]["PreToolUse"] = filtered
                else:
                    data["PreToolUse"] = filtered
                data.pop("_secret_broker_hook", None)
                write_json(hooks_path, data)
        return InstallResult(
            harness=self.id,
            scope=scope,
            paths_touched=[str(cfg), str(hooks_path)],
            detail="removed" if removed else "cleaned",
        )

    def _ensure_features_hooks(self, cfg: Path) -> None:
        text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
        if "[features]" not in text:
            cfg.write_text(text.rstrip() + "\n\n[features]\nhooks = true\n", encoding="utf-8")
            return
        if "hooks" not in text:
            cfg.write_text(text.rstrip() + "\nhooks = true\n", encoding="utf-8")

    def _write_hooks(self, hooks_path: Path, script: Path) -> None:
        command = f"{sys.executable} {script}"
        data = {
            "_secret_broker_hook": HOOK_MARKER,
            "PreToolUse": [
                {
                    "matcher": "^Bash$|^Shell$|^local_shell$",
                    "hooks": [
                        {
                            "type": "command",
                            "command": command,
                            "timeout": 10,
                            "statusMessage": "secret-broker policy",
                        }
                    ],
                }
            ],
        }
        write_json(hooks_path, data)
