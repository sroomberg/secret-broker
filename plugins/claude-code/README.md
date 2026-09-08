# Claude Code plugin artifact

## Install (today)

```bash
secret-broker harness install claude-code --scope project --hooks
```

Writes project `.mcp.json` and `.claude/settings.json` PreToolUse hook.

## Native plugin shape (breakout)

When publishing as a Claude Code plugin, ship:

- `.mcp.json` / `plugin.json` bundling the MCP server
- `hooks/hooks.json` from this directory
- Hook script resolved at install time to `block_secret_read.py`

Prefer marketplace install over git submodules.
