"""Harness plugin protocol — TDD fixtures and expected behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from secret_broker.harness.base import Scope
from secret_broker.harness.registry import get_plugin, list_plugins


def test_registry_lists_expected_harnesses():
    ids = {p.id for p in list_plugins()}
    assert {
        "cursor",
        "claude-code",
        "codex",
        "opencode",
        "continue",
    }.issubset(ids)


def test_get_plugin_unknown_raises():
    with pytest.raises(KeyError):
        get_plugin("not-a-real-harness")


@pytest.fixture
def homes(tmp_path: Path) -> dict[str, Path]:
    home = tmp_path / "home"
    root = tmp_path / "project"
    home.mkdir()
    root.mkdir()
    return {"home": home, "root": root}


def _broker_cmd() -> list[str]:
    return ["secret-broker", "mcp"]


@pytest.mark.parametrize(
    "harness_id,user_marker,project_marker",
    [
        ("cursor", ".cursor/mcp.json", ".cursor/mcp.json"),
        ("claude-code", ".claude.json", ".mcp.json"),
        ("codex", ".codex/config.toml", ".codex/config.toml"),
        ("opencode", ".config/opencode/opencode.json", "opencode.json"),
        ("continue", ".continue/config.json", ".continue/config.json"),
    ],
)
def test_install_user_and_project_writes_mcp(
    homes: dict[str, Path],
    harness_id: str,
    user_marker: str,
    project_marker: str,
):
    plugin = get_plugin(harness_id)
    home, root = homes["home"], homes["root"]

    before = plugin.status(scope=Scope.USER, root=root, home=home)
    assert before.installed is False

    result = plugin.install(
        scope=Scope.USER,
        root=root,
        home=home,
        broker_command=_broker_cmd(),
        config_path=None,
        with_hooks=False,
    )
    assert result.mcp_installed is True
    user_path = home / user_marker
    assert user_path.exists()
    assert plugin.status(scope=Scope.USER, root=root, home=home).installed is True

    result_p = plugin.install(
        scope=Scope.PROJECT,
        root=root,
        home=home,
        broker_command=_broker_cmd(),
        config_path="/tmp/sb.toml",
        with_hooks=False,
    )
    assert result_p.mcp_installed is True
    project_path = root / project_marker
    assert project_path.exists()
    text = project_path.read_text(encoding="utf-8")
    assert "secret-broker" in text


@pytest.mark.parametrize("harness_id", ["cursor", "claude-code", "codex", "opencode", "continue"])
def test_uninstall_removes_only_secret_broker_entry(homes: dict[str, Path], harness_id: str):
    plugin = get_plugin(harness_id)
    home, root = homes["home"], homes["root"]
    plugin.install(
        scope=Scope.USER,
        root=root,
        home=home,
        broker_command=_broker_cmd(),
        config_path=None,
        with_hooks=False,
    )
    assert plugin.status(scope=Scope.USER, root=root, home=home).installed is True
    plugin.uninstall(scope=Scope.USER, root=root, home=home)
    assert plugin.status(scope=Scope.USER, root=root, home=home).installed is False


def test_claude_and_codex_install_hooks_when_requested(homes: dict[str, Path]):
    home, root = homes["home"], homes["root"]
    for harness_id in ("claude-code", "codex"):
        plugin = get_plugin(harness_id)
        assert plugin.supports_hooks is True
        result = plugin.install(
            scope=Scope.PROJECT,
            root=root,
            home=home,
            broker_command=_broker_cmd(),
            config_path=None,
            with_hooks=True,
        )
        assert result.hooks_installed is True
        status = plugin.status(scope=Scope.PROJECT, root=root, home=home)
        assert status.hooks is True


def test_cursor_hooks_not_supported_flag(homes: dict[str, Path]):
    plugin = get_plugin("cursor")
    assert plugin.supports_hooks is False
    result = plugin.install(
        scope=Scope.USER,
        root=homes["root"],
        home=homes["home"],
        broker_command=_broker_cmd(),
        config_path=None,
        with_hooks=True,
    )
    assert result.hooks_installed is False
