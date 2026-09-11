# Agent harness plugins

`secret-broker` installs into coding-agent harnesses as an **MCP server** (and optional **PreToolUse hooks** where the harness supports them).

**Packaging model:** publishable artifacts live in [`plugins/`](../plugins/README.md); Python installers live in `src/secret_broker/harness/`. Decision record: [`_plans/007-harness-plugin-publishing.md`](../_plans/007-harness-plugin-publishing.md).

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
secret-broker harness package --dest dist/plugins
```

`--home` / `--root` override paths (used in tests and CI).

Installers read `plugins/<id>/` artifacts and refuse unsupported `contract_version` (`plugins/CONTRACT.md`).

## Matrix

| Harness | Plugin id | Artifacts | MCP config | Hooks |
| --- | --- | --- | --- | --- |
| **Cursor** | `cursor` | `plugins/cursor/` | `~/.cursor/mcp.json` / `.cursor/mcp.json` | — |
| **Claude Code** | `claude-code` | `plugins/claude-code/` | `~/.claude.json` / `.mcp.json` | PreToolUse |
| **Codex** | `codex` | `plugins/codex/` | `~/.codex/config.toml` | `hooks.json` |
| **OpenCode** | `opencode` | `plugins/opencode/` | `opencode.json` | — |
| **Continue** | `continue` | `plugins/continue/` | `.continue/config.json` | — |

## Architecture

```text
plugins/<id>/          publishable manifests (marketplace-ready)
        │
        ▼
secret-broker harness install <id>     installer SDK (may leave the monorepo later)
        ├─ merge MCP fragment → harness config
        └─ optional hooks
                │
                ▼
secret-broker mcp      core (stays in this repo)
```

## Adding a harness

1. Add `plugins/<id>/plugin.json` + MCP fragment (+ hooks) per `plugins/CONTRACT.md`.
2. Failing tests in `tests/test_harness_plugins.py` and `tests/test_plugin_artifacts.py`.
3. Implement `HarnessPlugin` under `src/secret_broker/harness/`.
4. Register in `harness/registry.py`.
5. Document here.

## Publishing / breakout

| Phase | Approach |
| --- | --- |
| **Now** | Monorepo; `harness install`; assets in `plugins/` |
| **Next** | Per-plugin GitHub Release zips / marketplace packages |
| **Later** | Separate repos + registry versions; **or** delete in-tree plugins once marketplace is primary |
| **Avoid** | Git submodules |

## Security

Hooks are **best-effort** (same caveat as AWS `asm-exec`). The real boundary is: no reveal tool on the MCP surface + destination allowlists on `call`/`run`.
