"""TDD: harness CLI commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from secret_broker.cli.app import app

runner = CliRunner()


def test_harness_list():
    result = runner.invoke(app, ["harness", "list"])
    assert result.exit_code == 0
    assert "cursor" in result.stdout
    assert "claude-code" in result.stdout
    assert "codex" in result.stdout
    assert "opencode" in result.stdout


def test_harness_install_and_status(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    root = tmp_path / "proj"
    home.mkdir()
    root.mkdir()
    monkeypatch.setenv("HOME", str(home))
    result = runner.invoke(
        app,
        [
            "harness",
            "install",
            "cursor",
            "--scope",
            "user",
            "--home",
            str(home),
            "--root",
            str(root),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (home / ".cursor" / "mcp.json").exists()
    status = runner.invoke(
        app,
        [
            "harness",
            "status",
            "cursor",
            "--scope",
            "user",
            "--home",
            str(home),
            "--root",
            str(root),
        ],
    )
    assert status.exit_code == 0
    assert "installed" in status.stdout.lower() or "true" in status.stdout.lower()


def test_harness_install_all_with_hooks(tmp_path: Path):
    home = tmp_path / "home"
    root = tmp_path / "proj"
    home.mkdir()
    root.mkdir()
    result = runner.invoke(
        app,
        [
            "harness",
            "install",
            "--all",
            "--scope",
            "project",
            "--hooks",
            "--home",
            str(home),
            "--root",
            str(root),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (root / ".cursor" / "mcp.json").exists()
    assert (root / ".mcp.json").exists()
    assert (root / ".codex" / "config.toml").exists()
    assert (root / "opencode.json").exists()
