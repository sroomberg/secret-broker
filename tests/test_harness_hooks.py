"""TDD: shared PreToolUse hook blocks plaintext secret reads."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "secret_broker"
    / "harness"
    / "hooks"
    / "block_secret_read.py"
)


def _run(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def test_hook_allows_safe_command():
    proc = _run(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {
                "command": "secret-broker call --url https://example.com --ref secret://env/T"
            },
        }
    )
    assert proc.returncode == 0


def test_hook_blocks_aws_get_secret_value():
    proc = _run(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "aws secretsmanager get-secret-value --secret-id foo"},
        }
    )
    assert proc.returncode == 2
    assert "secret-broker" in proc.stderr.lower() or "secret-broker" in proc.stdout.lower()


def test_hook_blocks_op_read_and_vault_kv_get():
    for cmd in ("op read op://v/i/f", "vault kv get secret/foo"):
        proc = _run({"tool_name": "Bash", "tool_input": {"command": cmd}})
        assert proc.returncode == 2, cmd


def test_hook_ignores_non_bash_tools():
    proc = _run({"tool_name": "Edit", "tool_input": {"file_path": "x.py"}})
    assert proc.returncode == 0
