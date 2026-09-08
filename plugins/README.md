# Harness plugins (monorepo)

Publishable **artifacts** for agent harnesses live here. The Python installer in `src/secret_broker/harness/` reads these files and merges them into each product’s config.

See the decision record: [`_plans/007-harness-plugin-publishing.md`](../_plans/007-harness-plugin-publishing.md).  
Stable interface: [`CONTRACT.md`](CONTRACT.md).

## Layout

```text
plugins/
  CONTRACT.md
  <harness-id>/
    plugin.json          # id, contract_version, capabilities
    README.md            # human/agent install notes for that harness
    mcp.fragment.json    # MCP stdio launch fragment (or mcp.fragment.toml)
    hooks/               # optional PreToolUse bundles
```

## Rules

1. **No broker imports** inside plugin artifacts (JSON/hooks/docs only, plus optional small hook scripts).
2. Plugins launch the broker via CLI/MCP: `secret-broker mcp` (or `python -m secret_broker mcp`).
3. Bump `contract_version` in `plugin.json` when the expected MCP tools or hook protocol change.
4. When extracting a plugin to its own repo, move the whole `plugins/<id>/` directory; keep the contract file or depend on a published contract package.

## Breakout paths (ranked)

1. **Best:** publish to harness marketplace / package registry; remove from this repo.
2. **Good:** separate repo + versioned dependency consumed by the installer.
3. **Avoid:** git submodules.
