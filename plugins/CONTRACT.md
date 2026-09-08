# Plugin ↔ core contract

Plugins must not import `secret_broker` Python internals. They integrate only through:

## 1. MCP stdio server

| Field | Value |
| --- | --- |
| Transport | stdio |
| Command | `secret-broker` (PATH) or `python3 -m secret_broker` |
| Args | `["mcp"]` |
| Optional env | `SECRET_BROKER_CONFIG` → path to config.toml |

### Tools the plugin may rely on

- `list_secrets`, `describe_secret`, `api_call`, `run_command`, `list_stores`, `policy_show`, `audit_tail`

### Tools that must never exist

- `get_secret`, `reveal`, `read_secret`, or any tool returning secret bytes

## 2. Optional PreToolUse hook

- Script: `block_secret_read.py` (stdin JSON event, exit `0` allow / `2` deny)
- Deny message must steer to `secret-broker call` / MCP `api_call`
- Hooks are best-effort; policy allowlists remain authoritative

## 3. `plugin.json` schema

```json
{
  "id": "cursor",
  "name": "Cursor",
  "contract_version": 1,
  "supports_mcp": true,
  "supports_hooks": false,
  "mcp_fragment": "mcp.fragment.json"
}
```

`contract_version` **1** is current. Incompatible MCP/hook changes require a major bump; older installers should refuse newer contracts they do not understand.

## Compatibility promise

- Core may add MCP tools without bumping the contract.
- Renaming/removing tools or changing hook exit semantics → bump `contract_version`.
- Plugin packaging (marketplace zip layout) may change without a contract bump if MCP/hook behavior is unchanged.
