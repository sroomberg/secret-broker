# Plan: Writing & publishing harness plugins (monorepo → optional split)

**Status:** accepted; **near-term monorepo path implemented**  
**Related:** `004-harness-plugins-tdd.md`, `docs/HARNESSES.md`, `plugins/`

## Question

How should we write and publish agent-harness plugins (Cursor, Claude Code, Codex, OpenCode, Continue, …)? Keep them in this monorepo for now, but plan for breakout (submodules **or** full removal).

## Opinion (recommended route)

**Future-proof with a monorepo that has hard package boundaries and a tiny stable contract — then split via published packages, not git submodules.**

| Option | Verdict |
| --- | --- |
| **A. Monorepo + `plugins/<harness>/` artifacts + thin installer in core** (now) | **Do this.** Clear ownership, one CI, easy refactors, still extractable. |
| **B. Later: publish each plugin as its own package/release; core depends by version or docs-only** | **Preferred breakout.** Marketplace/registry is how Cursor/Claude/Codex users already install. |
| **C. Later: git submodules pointing at plugin repos** | **Avoid.** Painful DX, awkward CI/release, false sense of modularity. Use only as a last resort for private unpublished trees. |
| **D. Later: delete plugins from this repo entirely** | **Good end state** once install is “get plugin from marketplace / `npx` / `claude plugin install`”. Core remains MCP+CLI only. |

### Why not submodules?

Submodules freeze a commit of another repo inside this one. For plugins that change with each harness’s manifest format, you want **semver releases** and independent CI, not submodule SHA babysitting. Contributors clone one repo today; tomorrow they `pip`/`npm`/marketplace-install a plugin. Submodules optimize for neither.

### Why not keep forever as deep Python inside `secret_broker.harness` only?

That couples **publishable harness artifacts** (JSON manifests, hook bundles, marketplace metadata) to the **broker library**. Marketplace plugins are files + metadata; the installer is optional glue. Separating `plugins/` now makes an eventual extract a directory move + version bump, not an archaeology project.

## Architecture

```text
┌─────────────────────────────────────────────────────────┐
│  this monorepo (for now)                                │
│                                                         │
│  src/secret_broker/     core: Broker, MCP, CLI, adapters│
│  src/secret_broker/harness/   installer SDK (writes cfg)│
│  plugins/<id>/          publishable harness artifacts   │
│       plugin.json       identity + contract version     │
│       mcp.*             MCP launch fragment             │
│       hooks/            optional PreToolUse bundles     │
│       README.md         harness-specific install notes  │
└─────────────────────────────────────────────────────────┘
              │
              │  stable contract (plugins/CONTRACT.md)
              ▼
   harness only needs: how to start `secret-broker mcp`
                       + optional path to block_secret_read hook
```

**Rule:** plugin packages must not import broker internals. They may shell out to the `secret-broker` CLI/MCP entrypoint. Core may read plugin manifests as data files.

## How we write plugins (now)

1. Add `plugins/<harness-id>/` with `plugin.json` + MCP fragment (+ hooks if supported).
2. Keep/extend a `HarnessPlugin` installer under `src/secret_broker/harness/` that:
   - reads the fragment from `plugins/<id>/` (packaged into the wheel)
   - merges into the harness config paths
3. TDD in `tests/test_harness_plugins.py` + asset presence tests under `tests/test_plugin_artifacts.py`.
4. Document in `docs/HARNESSES.md` and `plugins/README.md`.

## How we publish plugins

### Near term (monorepo)

| Channel | What ships | How |
| --- | --- | --- |
| **PyPI `secret-broker`** | Core + installer + embedded `plugins/` assets | Publish workflow |
| **GitHub Release** | Per-plugin zip from `plugins/<id>/` | `secret-broker harness package` + publish workflow attaches zips |
| **In-tree CLI** | `secret-broker harness install <id>` | Reads artifacts; refuses unsupported `contract_version` |

**Near-term status:** implemented (installers wired to artifacts, contract gate, CI validate/package, release zip attach).

### Medium term (still monorepo, separate versioning)

- Tag plugins independently: `plugin-cursor-v0.1.0`, or use a `plugins/<id>/VERSION` file.
- CI matrix: build/validate each `plugins/<id>` on PR; publish plugin zips on tag.
- Optional: publish `secret-broker-plugin-claude-code` as a tiny Python/npm package that only contains manifests + a post-install script.

### Long term (breakout)

1. Move `plugins/<id>` → `sroomberg/secret-broker-plugin-<id>` (or a `plugins` org repo per harness).
2. Publish to the **harness marketplace** when available (Claude Code plugins, Cursor marketplace, Codex plugin manifest, etc.).
3. In core:
   - **Preferred:** drop in-tree assets; installer becomes a thin client (“download release X / open marketplace”).
   - **Or:** depend on a versioned package (`secret-broker-plugin-cursor>=1`).
   - **Not preferred:** git submodule pin.
4. If a harness dies or the marketplace is enough, **delete** the installer path for that id from core (option D). No submodule left to rot.

## Contract versioning

`plugins/CONTRACT.md` defines `contract_version`. Breaking changes (MCP tool renames, hook exit codes) bump the contract; plugins declare compatibility. Core CLI refuses to install a plugin with an unsupported contract version.

## Decision record

- **Now:** monorepo; artifacts under `plugins/`; installers in `secret_broker.harness`.
- **Breakout:** published packages / marketplaces.
- **Submodules:** only if a plugin must stay private and cannot be published — revisit then; do not design for it.
- **Removal:** allowed and desirable once external install is primary.
