"""Load publishable plugin artifacts from the monorepo `plugins/` tree."""

from __future__ import annotations

import json
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
    # importlib.resources fallback for installed package
    try:
        base = resources.files("secret_broker") / "plugin_artifacts"
        # Traversable → Path when possible
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


def list_artifact_ids() -> list[str]:
    root = repo_plugins_root()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "plugin.json").is_file())


def packaged_hook_fallback() -> Path:
    """Hook script shipped inside the Python package (always available)."""
    return Path(__file__).resolve().parent / "hooks" / "block_secret_read.py"
