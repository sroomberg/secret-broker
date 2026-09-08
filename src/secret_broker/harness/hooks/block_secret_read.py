#!/usr/bin/env python3
"""PreToolUse hook: block plaintext secret-read CLIs; steer agents to secret-broker.

Exit 0 = allow. Exit 2 = block (Claude Code / Codex convention) with reason on stderr.
Reads hook event JSON from stdin. Never prints secret values.
"""

from __future__ import annotations

import json
import re
import sys

BLOCK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\baws\b.*\bget-secret-value\b", re.I),
    re.compile(r"\baws\b.*\bbatch-get-secret-value\b", re.I),
    re.compile(r"\bGetSecretValue\b"),
    re.compile(r"\bop\s+read\b", re.I),
    re.compile(r"\bop\s+item\s+get\b", re.I),
    re.compile(r"\bvault\s+kv\s+get\b", re.I),
    re.compile(r"\bvault\s+read\b", re.I),
    re.compile(r"\bdoppler\s+secrets\s+get\b", re.I),
    re.compile(r"\binfisical\s+secrets\s+get\b", re.I),
    re.compile(r"\bagentsecrets\s+secrets\s+(get|show)\b", re.I),
    re.compile(r"\bprintenv\b.+\b(TOKEN|SECRET|PASSWORD|API_KEY)\b", re.I),
]

REASON = (
    "Blocked: plaintext secret read. Use secret-broker call/run (or the MCP api_call / "
    "run_command tools) so the value never enters agent context."
)


def _command_from_payload(payload: dict) -> str:
    tool = str(payload.get("tool_name") or payload.get("tool") or "")
    if tool and tool not in {"Bash", "bash", "Shell", "shell", "local_shell"}:
        return ""
    inp = payload.get("tool_input") or payload.get("input") or {}
    if isinstance(inp, dict):
        for key in ("command", "cmd", "script"):
            if key in inp and isinstance(inp[key], str):
                return inp[key]
    if isinstance(payload.get("command"), str):
        return payload["command"]
    return ""


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    command = _command_from_payload(payload)
    if not command:
        return 0
    for pat in BLOCK_PATTERNS:
        if pat.search(command):
            print(REASON, file=sys.stderr)
            # Some harnesses also read stdout JSON decisions
            print(json.dumps({"decision": "deny", "reason": REASON}))
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
