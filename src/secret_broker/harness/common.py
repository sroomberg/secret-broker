"""Shared helpers for editing harness config files."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from secret_broker.harness.base import SERVER_NAME


def mcp_stdio_entry(
    broker_command: list[str],
    *,
    config_path: str | None = None,
    style: str = "cursor",
) -> dict[str, Any]:
    """Build an MCP stdio server entry for common harness formats."""
    if not broker_command:
        raise ValueError("broker_command required")
    command, *args = broker_command
    env: dict[str, str] = {}
    if config_path:
        env["SECRET_BROKER_CONFIG"] = config_path

    if style == "opencode":
        entry: dict[str, Any] = {
            "type": "local",
            "command": list(broker_command),
            "enabled": True,
        }
        if env:
            entry["environment"] = env
        return entry

    if style == "claude":
        entry = {"command": command, "args": args}
        if env:
            entry["env"] = env
        return entry

    # cursor / continue default
    entry = {"command": command, "args": args}
    if env:
        entry["env"] = env
    return entry


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def merge_mcp_servers_json(
    path: Path,
    *,
    entry: dict[str, Any],
    key: str = "mcpServers",
    server_name: str = SERVER_NAME,
) -> None:
    data = read_json(path)
    servers = data.get(key)
    if not isinstance(servers, dict):
        servers = {}
    servers[server_name] = entry
    data[key] = servers
    write_json(path, data)


def remove_mcp_server_json(
    path: Path,
    *,
    key: str = "mcpServers",
    server_name: str = SERVER_NAME,
) -> bool:
    if not path.exists():
        return False
    data = read_json(path)
    servers = data.get(key)
    if not isinstance(servers, dict) or server_name not in servers:
        return False
    del servers[server_name]
    data[key] = servers
    write_json(path, data)
    return True


def json_has_server(path: Path, *, key: str = "mcpServers", server_name: str = SERVER_NAME) -> bool:
    if not path.exists():
        return False
    data = read_json(path)
    servers = data.get(key)
    return isinstance(servers, dict) and server_name in servers


_TOML_SERVER_RE = re.compile(
    rf"^\[mcp_servers\.{re.escape(SERVER_NAME)}\](.*?)^(?=\[|\Z)",
    re.MULTILINE | re.DOTALL,
)


def upsert_codex_mcp(path: Path, broker_command: list[str], config_path: str | None) -> None:
    """Insert or replace [mcp_servers.secret-broker] in a Codex config.toml."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    # Remove prior block
    cleaned = _TOML_SERVER_RE.sub("", existing).rstrip() + "\n"
    command, *args = broker_command
    lines = [
        f"[mcp_servers.{SERVER_NAME}]",
        f'command = "{_toml_escape(command)}"',
        f"args = {_toml_array(args)}",
        "enabled = true",
    ]
    if config_path:
        lines.append("")
        lines.append(f"[mcp_servers.{SERVER_NAME}.env]")
        lines.append(f'SECRET_BROKER_CONFIG = "{_toml_escape(config_path)}"')
    block = "\n".join(lines) + "\n"
    if cleaned.strip():
        path.write_text(cleaned.rstrip() + "\n\n" + block, encoding="utf-8")
    else:
        path.write_text(block, encoding="utf-8")


def remove_codex_mcp(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if f"[mcp_servers.{SERVER_NAME}]" not in text:
        return False
    cleaned = _TOML_SERVER_RE.sub("", text)
    # Also drop env subtable if left behind
    cleaned = re.sub(
        rf"^\[mcp_servers\.{re.escape(SERVER_NAME)}\.env\](.*?)^(?=\[|\Z)",
        "",
        cleaned,
        flags=re.MULTILINE | re.DOTALL,
    )
    path.write_text(cleaned.strip() + ("\n" if cleaned.strip() else ""), encoding="utf-8")
    return True


def codex_has_server(path: Path) -> bool:
    if not path.exists():
        return False
    return f"[mcp_servers.{SERVER_NAME}]" in path.read_text(encoding="utf-8")


def hook_script_path() -> Path:
    return Path(__file__).resolve().parent / "hooks" / "block_secret_read.py"


def install_hook_script(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    src = hook_script_path()
    dest = dest_dir / "block_secret_read.py"
    shutil.copy2(src, dest)
    os.chmod(dest, 0o755)
    return dest


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(f'"{_toml_escape(v)}"' for v in values) + "]"
