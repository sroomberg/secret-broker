# Cursor plugin artifact

## Install (today)

```bash
secret-broker harness install cursor --scope project
# writes .cursor/mcp.json
```

## Manual

Copy `mcp.fragment.json` into `.cursor/mcp.json` under `mcpServers.secret-broker` (drop `${SECRET_BROKER_CONFIG}` or set it).

## Breakout

Publish as a Cursor marketplace / zip from this directory. Core installer can then fetch a release instead of embedding assets.
