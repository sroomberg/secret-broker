# Plan: Federated facade (build)

**Status:** implemented  
**Depends on:** `002` spike failure (no existing federated front-end)

## Goal

Ship `secret-broker` as a **facade, not a vault**. Live-read AWS Secrets Manager, 1Password, and HashiCorp Vault (plus env/memory for demos). CLI and MCP are equal surfaces over one broker library so a policy hole cannot exist on only one path.

## Non-goals

- New encrypted local vault competing with ClauLock / AgentSecrets
- `reveal` / `get` / `cat` / `show` for humans (use native store CLIs)
- Ruby/EasyPost gem unless required later

## Adapters (v1)

| Alias | Backend | Ref form |
| --- | --- | --- |
| `env` | process env | `secret://env/VAR` |
| `memory` | in-process (tests/doctor) | `secret://memory/NAME` |
| `aws` | AWS Secrets Manager | `secret://aws/<id>#<json-key>` |
| `op` | 1Password via `op` | `secret://op/<vault>/<item>/<field>` |
| `vault` | Vault KV | `secret://vault/<mount>/<path>#<field>` |

## Core modules

- `refs` — parse `secret://…`
- `policy` — deny-by-default hosts; bin allowlists; SSRF guards
- `audit` — JSONL, no value field
- `redact` — scrub plaintext + common encodings from responses
- `broker` — `list`, `describe`, `call`, `run`, `doctor`
- `cli` (Typer) + `mcp_server` — both import `Broker`

## Acceptance

- [x] No reveal API on CLI or MCP
- [x] Off-allowlist host denied before resolve
- [x] `run` / `call` redaction self-check in `doctor`
- [x] Audit events never contain secret bytes
- [x] Package installable; `secret-broker --help` exposes planned commands

## Follow-ons

- Harness installers (`004`)
- CI / PyPI (`005`)
