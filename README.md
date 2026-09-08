# Secret broker

Federated **facade** (not a vault) so AI agents can use secrets from AWS Secrets Manager, 1Password, HashiCorp Vault, and env — **without ever reading plaintext**.

Agents get `secret://…` references. A trusted broker process resolves the value and injects it into an HTTP call or child process. Values never appear in MCP results, chat, audit logs, or error strings.

## Why this exists

A 2026 spike (`SPIKE.md`) checked ClauLock, AgentSecrets, `asm-exec`, and `op run`.

- Those tools correctly implement **references in / values never out**.
- Most are a **new store**, not a front-end to stores you already trust.
- AgentSecrets docs claim AWS-as-source-of-truth delivery; **source code only reads the OS keychain** (copy-in via `secrets set` / `pull`).
- No existing tool live-reads **AWS + 1Password + Vault** behind one allowlisted inject API.

So this repo is the thin federated adapter layer.

## Security invariant

Secret bytes exist only inside the broker/wrapper process. HTTP inject without a destination allowlist is a confused deputy and is **denied by default**.

There is **no** `get` / `cat` / `show` / `reveal` command or MCP tool.

## Install

```bash
pip install -e '.[dev]'
# optional adapters
pip install -e '.[aws,vault]'
```

Copy `examples/config.example.toml` to `~/.config/secret-broker/config.toml` and enable the stores you use.

## CLI

```bash
secret-broker stores
secret-broker list
secret-broker describe secret://aws/my-app/db
secret-broker policy show
secret-broker policy allow-host api.github.com
secret-broker policy allow-bin curl

# HTTP inject (prints redacted downstream body only)
secret-broker call --url https://api.github.com/user \
  --ref secret://env/GITHUB_TOKEN --inject bearer

# Env inject into a child process
secret-broker run --ref TOKEN=secret://memory/TOKEN -- python3 -c 'import os; print("ok")'

secret-broker audit
secret-broker doctor
secret-broker mcp          # stdio MCP for any harness

# Install into agent harnesses (Cursor, Claude Code, Codex, OpenCode, Continue)
secret-broker harness list
secret-broker harness install cursor
secret-broker harness install claude-code --hooks
secret-broker harness install --all --scope project --hooks
```

Shell completions: `secret-broker --install-completion`

Harness details: [`docs/HARNESSES.md`](docs/HARNESSES.md).

### Reference forms

| Backend | Example |
| --- | --- |
| Env | `secret://env/MY_TOKEN` |
| Memory (tests) | `secret://memory/NAME` |
| AWS SM | `secret://aws/<secret-id>#<json-key>` |
| 1Password | `secret://op/<vault>/<item>/<field>` |
| Vault KV | `secret://vault/<mount>/<path>#<field>` |

## MCP + harness plugins

Prefer the installer (writes the correct file for each product):

```bash
secret-broker harness install cursor
# or: claude-code | codex | opencode | continue
```

Manual Cursor example (`.cursor/mcp.json` / `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "secret-broker": {
      "command": "secret-broker",
      "args": ["mcp"]
    }
  }
}
```

Tools: `list_secrets`, `describe_secret`, `api_call`, `run_command`, `list_stores`, `policy_show`, `audit_tail`.  
**Not provided:** anything that returns secret bytes.

Claude Code / Codex can also install a **PreToolUse** hook (`--hooks`) that blocks `aws get-secret-value`, `op read`, `vault kv get`, etc., and steers the agent back to `secret-broker`.

## Architecture

```text
Cursor / Claude Code / Codex / OpenCode / Continue / CLI
    │  refs only (+ optional PreToolUse hooks)
    ▼
secret-broker (Typer CLI  ≡  MCP  ≡  harness plugins)
    │  shared Broker library
    ├─ policy (host/bin allowlists)
    ├─ audit JSONL (no value field)
    └─ adapters: aws | op | vault | env | memory
           │ live-read at use time
           ▼
     your existing stores
```

CLI, MCP, and harness installers share the same broker so a policy hole cannot exist on only one surface.

## Development (TDD)

```bash
pip install -e '.[dev]'
pytest -q
# New harness: failing test in tests/test_harness_plugins.py → implement plugin → register
```

## Python vs Ruby

Python. Ruby only if this must ship as an EasyPost gem.

## License

MIT — see `LICENSE`.
