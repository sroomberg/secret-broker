"""Load publishable plugin artifacts from the monorepo `plugins/` tree."""

from __future__ import annotations

import json
import zipfile
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

SUPPORTED_CONTRACT_VERSION = 1


class PluginArtifactError(RuntimeError):
    """Invalid or incompatible harness plugin artifact."""


def repo_plugins_root() -> Path:
    """Resolve plugin artifacts: source tree first, then packaged wheel data."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "plugins",  # <root>/src/secret_broker/harness/assets.py
        here.parents[2] / "plugins",
        Path.cwd() / "plugins",
        Path(__file__).resolve().parents[1] / "plugin_artifacts",  # wheel force-include
    ]
    for path in candidates:
        if (path / "CONTRACT.md").is_file() or (path.is_dir() and any(path.glob("*/plugin.json"))):
            return path
    try:
        base = resources.files("secret_broker") / "plugin_artifacts"
        root = Path(str(base))
        if root.is_dir():
            return root
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        pass
    return candidates[0]


def plugin_dir(plugin_id: str) -> Path:
    path = repo_plugins_root() / plugin_id
    if not path.is_dir():
        raise PluginArtifactError(f"plugin artifacts missing: {plugin_id}")
    return path


@lru_cache(maxsize=16)
def load_plugin_json(plugin_id: str) -> dict[str, Any]:
    path = plugin_dir(plugin_id) / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PluginArtifactError(f"plugin.json must be an object: {plugin_id}")
    version = int(data.get("contract_version", 0))
    if version != SUPPORTED_CONTRACT_VERSION:
        raise PluginArtifactError(
            f"plugin {plugin_id} contract_version={version} "
            f"unsupported (need {SUPPORTED_CONTRACT_VERSION})"
        )
    if data.get("id") != plugin_id:
        raise PluginArtifactError(
            f"plugin id mismatch: directory={plugin_id} json={data.get('id')}"
        )
    return data


def load_mcp_fragment(plugin_id: str) -> dict[str, Any] | str:
    meta = load_plugin_json(plugin_id)
    name = meta.get("mcp_fragment", "mcp.fragment.json")
    path = plugin_dir(plugin_id) / name
    text = path.read_text(encoding="utf-8")
    if name.endswith(".json"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise PluginArtifactError(f"MCP fragment must be a JSON object: {plugin_id}")
        return data
    return text


def load_hooks_fragment(plugin_id: str) -> dict[str, Any] | None:
    meta = load_plugin_json(plugin_id)
    if not meta.get("supports_hooks"):
        return None
    name = meta.get("hooks_fragment")
    if not name:
        return None
    path = plugin_dir(plugin_id) / name
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PluginArtifactError(f"hooks fragment must be a JSON object: {plugin_id}")
    return data


def materialize_mcp_entry(
    plugin_id: str,
    *,
    broker_command: list[str],
    config_path: str | None,
    style: str,
) -> dict[str, Any]:
    """Load artifact MCP fragment, enforce contract, apply runtime command/config."""
    if not broker_command:
        raise ValueError("broker_command required")
    meta = load_plugin_json(plugin_id)
    if not meta.get("supports_mcp", True):
        raise PluginArtifactError(f"plugin {plugin_id} does not support MCP")

    fragment = load_mcp_fragment(plugin_id)
    if isinstance(fragment, str):
        # TOML fragments (Codex) are applied by upsert_codex_mcp; callers use ensure only.
        raise PluginArtifactError(
            f"plugin {plugin_id} uses a non-JSON MCP fragment; use upsert path"
        )

    entry = dict(fragment)
    if style == "opencode":
        entry["type"] = "local"
        entry["command"] = list(broker_command)
        entry["enabled"] = bool(entry.get("enabled", True))
        env = dict(entry.get("environment") or {})
        env.pop("SECRET_BROKER_CONFIG", None)
        if config_path:
            env["SECRET_BROKER_CONFIG"] = config_path
        if env:
            entry["environment"] = env
        else:
            entry.pop("environment", None)
        return entry

    command, *args = broker_command
    entry["command"] = command
    entry["args"] = list(args)
    env = dict(entry.get("env") or {})
    # Drop template placeholders from checked-in fragments
    if env.get("SECRET_BROKER_CONFIG", "").startswith("${"):
        env.pop("SECRET_BROKER_CONFIG", None)
    if config_path:
        env["SECRET_BROKER_CONFIG"] = config_path
    if env:
        entry["env"] = env
    else:
        entry.pop("env", None)
    return entry


def ensure_plugin_contract(plugin_id: str) -> dict[str, Any]:
    """Validate artifacts before install (JSON or TOML MCP fragments)."""
    return load_plugin_json(plugin_id)


def list_artifact_ids() -> list[str]:
    root = repo_plugins_root()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "plugin.json").is_file())


def packaged_hook_fallback() -> Path:
    """Hook script shipped inside the Python package (always available)."""
    return Path(__file__).resolve().parent / "hooks" / "block_secret_read.py"


def package_plugin_zips(dest_dir: Path, *, plugin_ids: list[str] | None = None) -> list[Path]:
    """Zip each plugins/<id>/ tree for GitHub Releases (near-term publish channel)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    ids = plugin_ids or list_artifact_ids()
    out: list[Path] = []
    for plugin_id in ids:
        ensure_plugin_contract(plugin_id)
        src = plugin_dir(plugin_id)
        zip_path = dest_dir / f"secret-broker-plugin-{plugin_id}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(src.rglob("*")):
                if path.is_file():
                    zf.write(path, arcname=str(Path(plugin_id) / path.relative_to(src)))
            # Include contract for consumers of the zip
            contract = repo_plugins_root() / "CONTRACT.md"
            if contract.is_file():
                zf.write(contract, arcname="CONTRACT.md")
        out.append(zip_path)
    return out
