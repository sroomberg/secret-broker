# Plan: Agent harness plugins (TDD)

**Status:** implemented  
**Depends on:** `003` broker core

## Goal

Plan for plugins that install `secret-broker` into agent harnesses (Cursor, OpenCode, Claude Code, Codex, Continue, …). Build with **TDD**: failing harness tests first, then plugin implementations.

## Why

MCP alone is not enough UX. Each product stores MCP (and sometimes hooks) in different files. A `harness install` command should write the right config and optionally register PreToolUse hooks that block plaintext secret CLIs.

## Plugin protocol

```text
HarnessPlugin
  id, name, supports_mcp, supports_hooks
  status(scope, root, home) → installed / mcp / hooks / paths
  install(..., broker_command, config_path, with_hooks)
  uninstall(...)
```

Scopes: `user` | `project`.

## Target matrix

| Harness | MCP path (user / project) | Hooks |
| --- | --- | --- |
| Cursor | `~/.cursor/mcp.json` / `.cursor/mcp.json` | no |
| Claude Code | `~/.claude.json` / `.mcp.json` | `.claude/settings.json` PreToolUse |
| Codex | `~/.codex/config.toml` | `.codex/hooks.json` |
| OpenCode | `~/.config/opencode/opencode.json` / `opencode.json` | no |
| Continue | `~/.continue/config.json` | no |

## Shared hook

`block_secret_read.py` — stdin JSON PreToolUse handler; exit `2` to deny:

- `aws … get-secret-value` / `batch-get-secret-value`
- `op read` / `op item get`
- `vault kv get` / `vault read`
- similar Doppler / Infisical / AgentSecrets show paths

Steer agents to `secret-broker call` / MCP `api_call`. Hooks are **best-effort** (same caveat as AWS `asm-exec`); allowlists remain the real boundary.

## CLI

```bash
secret-broker harness list
secret-broker harness install <id> [--scope user|project] [--hooks]
secret-broker harness install --all --scope project --hooks
secret-broker harness status <id>
secret-broker harness uninstall <id>
```

## TDD sequence

1. RED: `tests/test_harness_plugins.py`, `test_harness_hooks.py`, `test_harness_cli.py`
2. GREEN: `secret_broker/harness/*` + registry + CLI group
3. Docs: `docs/HARNESSES.md`, `docs/CONTRIBUTING.md`

## Adding a harness later

1. Failing path markers in `test_harness_plugins.py`
2. Implement `HarnessPlugin` subclass
3. Register in `harness/registry.py`
4. Update `docs/HARNESSES.md` and this plan’s matrix
