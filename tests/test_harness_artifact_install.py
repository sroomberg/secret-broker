"""TDD: installers must use plugins/ artifacts and enforce contract_version."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from secret_broker.harness.assets import (
    PluginArtifactError,
    load_plugin_json,
    materialize_mcp_entry,
)
from secret_broker.harness.base import Scope
from secret_broker.harness.cursor import CursorPlugin
from secret_broker.harness.registry import get_plugin


def test_materialize_overrides_command_and_strips_placeholder_env():
    entry = materialize_mcp_entry(
        "cursor",
        broker_command=["/usr/bin/secret-broker", "mcp"],
        config_path=None,
        style="cursor",
    )
    assert entry["command"] == "/usr/bin/secret-broker"
    assert entry["args"] == ["mcp"]
    assert "env" not in entry or "SECRET_BROKER_CONFIG" not in entry.get("env", {})


def test_materialize_sets_config_env():
    entry = materialize_mcp_entry(
        "cursor",
        broker_command=["secret-broker", "mcp"],
        config_path="/tmp/sb.toml",
        style="cursor",
    )
    assert entry["env"]["SECRET_BROKER_CONFIG"] == "/tmp/sb.toml"


def test_materialize_opencode_uses_command_array():
    entry = materialize_mcp_entry(
        "opencode",
        broker_command=["secret-broker", "mcp"],
        config_path="/tmp/c.toml",
        style="opencode",
    )
    assert entry["type"] == "local"
    assert entry["command"] == ["secret-broker", "mcp"]
    assert entry["environment"]["SECRET_BROKER_CONFIG"] == "/tmp/c.toml"


def test_materialize_refuses_bad_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "plugins"
    bad = root / "cursor"
    bad.mkdir(parents=True)
    (bad / "plugin.json").write_text(
        json.dumps(
            {
                "id": "cursor",
                "name": "Cursor",
                "contract_version": 99,
                "supports_mcp": True,
                "supports_hooks": False,
                "mcp_fragment": "mcp.fragment.json",
            }
        ),
        encoding="utf-8",
    )
    (bad / "mcp.fragment.json").write_text(
        json.dumps({"command": "secret-broker", "args": ["mcp"]}),
        encoding="utf-8",
    )
    (root / "CONTRACT.md").write_text("# contract\n", encoding="utf-8")
    monkeypatch.setattr(
        "secret_broker.harness.assets.repo_plugins_root",
        lambda: root,
    )
    load_plugin_json.cache_clear()
    with pytest.raises(PluginArtifactError, match="contract_version"):
        materialize_mcp_entry(
            "cursor",
            broker_command=["secret-broker", "mcp"],
            config_path=None,
            style="cursor",
        )
    load_plugin_json.cache_clear()


def test_cursor_install_uses_artifact_backed_entry(tmp_path: Path):
    home = tmp_path / "home"
    root = tmp_path / "proj"
    home.mkdir()
    root.mkdir()
    plugin = CursorPlugin()
    plugin.install(
        scope=Scope.USER,
        root=root,
        home=home,
        broker_command=["/opt/sb", "mcp"],
        config_path="/etc/sb.toml",
        with_hooks=False,
    )
    data = json.loads((home / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    entry = data["mcpServers"]["secret-broker"]
    assert entry["command"] == "/opt/sb"
    assert entry["args"] == ["mcp"]
    assert entry["env"]["SECRET_BROKER_CONFIG"] == "/etc/sb.toml"


def test_install_all_registry_plugins_load_contract():
    for plugin in (
        get_plugin(i) for i in ("cursor", "claude-code", "codex", "opencode", "continue")
    ):
        meta = load_plugin_json(plugin.id)
        assert meta["contract_version"] == 1


def test_package_plugin_zips(tmp_path: Path):
    from secret_broker.harness.assets import package_plugin_zips

    zips = package_plugin_zips(tmp_path / "out")
    names = {p.name for p in zips}
    assert "secret-broker-plugin-cursor.zip" in names
    assert "secret-broker-plugin-claude-code.zip" in names
    # zip contains plugin.json
    import zipfile

    with zipfile.ZipFile(tmp_path / "out" / "secret-broker-plugin-cursor.zip") as zf:
        names_in = zf.namelist()
        assert "cursor/plugin.json" in names_in
        assert "CONTRACT.md" in names_in
