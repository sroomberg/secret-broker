"""TDD: monorepo plugin artifacts + contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from secret_broker.harness.assets import (
    SUPPORTED_CONTRACT_VERSION,
    list_artifact_ids,
    load_mcp_fragment,
    load_plugin_json,
    repo_plugins_root,
)
from secret_broker.harness.registry import list_plugins

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"


def test_plugins_tree_and_contract_exist():
    assert (PLUGINS / "README.md").is_file()
    assert (PLUGINS / "CONTRACT.md").is_file()
    assert repo_plugins_root() == PLUGINS


def test_every_registry_plugin_has_artifacts():
    ids = {p.id for p in list_plugins()}
    artifacts = set(list_artifact_ids())
    assert ids <= artifacts, f"missing artifacts for {ids - artifacts}"


@pytest.mark.parametrize("plugin_id", ["cursor", "claude-code", "codex", "opencode", "continue"])
def test_plugin_json_contract(plugin_id: str):
    meta = load_plugin_json(plugin_id)
    assert meta["contract_version"] == SUPPORTED_CONTRACT_VERSION
    assert meta["supports_mcp"] is True
    fragment = load_mcp_fragment(plugin_id)
    blob = str(fragment) if isinstance(fragment, dict) else fragment
    assert "secret-broker" in blob or "mcp" in blob.lower()


def test_hook_capable_plugins_ship_hooks_fragment():
    for plugin_id in ("claude-code", "codex"):
        meta = load_plugin_json(plugin_id)
        assert meta["supports_hooks"] is True
        assert "hooks_fragment" in meta
        path = PLUGINS / plugin_id / meta["hooks_fragment"]
        assert path.is_file()
