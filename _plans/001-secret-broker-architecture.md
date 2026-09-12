# Plan: Secret broker architecture

**Status:** accepted  
**Origin:** product request — plugin that connects any secrets store so an agent can use secrets without reading plaintext; plus a fully functional CLI.

## Problem

AI agents that can call tools will eventually see any secret that enters their context (prompt injection, logs, tool transcripts). Traditional “fetch then use” secrets APIs (`get-secret-value`, MCP `read_secret`) are the wrong threat model.

## Invariant

Secret bytes exist only in a trusted broker/wrapper process. They never appear in:

- MCP tool results
- chat / model context
- audit logs
- error strings

HTTP inject without a destination allowlist is a confused deputy and is not acceptable.

## Shape

```text
Agent (Cursor / Claude Code / …)
    │  secret:// refs only
    ▼
CLI  ≡  MCP  (same Broker library)
    ├─ policy (host / bin allowlists)
    ├─ audit (no value field)
    └─ adapters → existing stores (live-read)
```

Agents orchestrate; the broker injects at HTTP or child-process boundaries and redacts echoes.

## Surfaces (equal)

### CLI (`secret-broker`, Typer)

- `list` / `describe <ref>` — names, backend, allowed ops; never values
- `call` — HTTP inject (`--method`, `--url`, `--ref`, `--inject bearer|header:…`)
- `run --ref NAME=secret://… -- <command>` — env inject; scrub stdout/stderr
- `policy show|allow-host|allow-bin`
- `audit` — who / ref / destination / time; no value field
- `stores` — adapter health
- `mcp` — stdio MCP server
- `doctor` — auth, policy, leak self-check
- shell completions

**Out of scope for v1:** `get` / `cat` / `show` / `reveal`.

### MCP

Thin wrapper over the same broker commands. No `get_secret` tool.

## Language

Python unless this must ship as an EasyPost Ruby gem.

## Repo

Private GitHub: `sroomberg/secret-broker`. Work in cloud, not on an unauthenticated local Mac.
