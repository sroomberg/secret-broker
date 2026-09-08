# Agent harness plugins

`secret-broker` installs into coding-agent harnesses as an **MCP server** (and optional **PreToolUse hooks** where the harness supports them). The broker core stays harness-agnostic; each plugin only knows how to edit that product’s config files.

## Install

```bash
# one harness (user scope)
secret-broker harness install cursor
secret-broker harness install claude-code --hooks
secret-broker harness install codex --hooks

# every known harness into the current project
secret-broker harness install --all --scope project --hooks

secret-broker harness list
secret-broker harness status cursor
secret-broker harness uninstall cursor
```

`--home` / `--root` override paths (used in tests and CI).

## Matrix

| Harness | Plugin id | MCP config | Hooks | Notes |
| --- | --- | --- | --- | --- |
| **Cursor** | `cursor` | `~/.cursor/mcp.json` or `.cursor/mcp.json` | — | MCP only |
| **Claude Code** | `claude-code` | `~/.claude.json` or project `.mcp.json` | `.claude/settings.json` PreToolUse | Blocks plaintext secret CLIs |
| **Codex** | `codex` | `~/.codex/config.toml` or `.codex/config.toml` | `.codex/hooks.json` | Enables `[features] hooks` |
| **OpenCode** | `opencode` | `~/.config/opencode/opencode.json` or `opencode.json` | — | `mcp` local command array |
| **Continue** | `continue` | `~/.continue/config.json` or `.continue/config.json` | — | MCP only |

## Architecture

```text
secret-broker harness install <id>
        │
        ▼
 HarnessPlugin.install()
        ├─ write MCP entry → secret-broker mcp
        └─ optional: copy block_secret_read.py + register PreToolUse
                │
                ▼
 Agent never gets get_secret; hook denies aws get-secret-value / op read / vault kv get
```

Adding a harness:

1. Write failing tests in `tests/test_harness_plugins.py` (path markers + install/uninstall).
2. Implement `secret_broker/harness/<name>.py` extending `HarnessPlugin`.
3. Register in `harness/registry.py`.
4. Document in this file.

## Security

Hooks are **best-effort** (same caveat as AWS `asm-exec`). The real boundary is: no reveal tool on the MCP surface + destination allowlists on `call`/`run`. Hooks only steer agents away from native store CLIs that dump plaintext.
