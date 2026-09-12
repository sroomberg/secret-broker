# Spike: existing tools vs federated secret broker

**Date:** 2026-09-08  
**Decision:** **Build the federated facade.** No existing tool live-reads AWS + 1Password + Vault without becoming a new store.

## Question

Can one plugin sit in front of existing secret stores (AWS SM, 1Password, Vault, …) so agents get **references**, a trusted process **uses** the secret, and **no `get_secret` / plaintext** appears in MCP or chat?

## What we checked

| Tool | MCP + inject + no get | Own store? | Live-reads AWS/Vault/1P? | CLI coverage |
| --- | --- | --- | --- | --- |
| **ClauLock (`clsec`)** | Yes — placeholders at `execve`, never-reveal MCP | Yes (`~/.clsec/`) | **No** | Strong local vault UX; not multi-store |
| **AgentSecrets** | Yes — `api_call`, `list_secrets`, proxy, redaction | Yes (OS keychain + their cloud) | **Docs claim yes; source says no** | `call`, `env`, `secrets`, `logs`, `mcp`, allowlists. No `stores` / multi-adapter / `doctor` |
| **AWS `asm-exec`** | Wrapper + hook (best-effort) | N/A (AWS SM) | AWS only | AWS-only; Cursor secondary |
| **1Password `op run`** | Inject into child | 1Password vault | 1P only | Store-native CLI |
| **Doppler / Infisical / Keeper** | Prefer `run`/`exec` | Their store | Not a multi-store front-end | Prefer wrappers; avoid MCP that dumps values |
| **HashiCorp Vault MCP** | Has `read_secret` | Vault | Wrong threat model | Do not use for agents |

## AgentSecrets AWS claim — verified false (in code)

Marketing ([vs AWS Secrets Manager](https://agentsecrets.tech/docs/comparisons/vs-aws-secrets-manager)):

> Store secrets in AWS, then configure the AgentSecrets proxy to resolve from AWS…

**Source inspection** (`The-17/agentsecrets`, main @ spike):

- Proxy resolves via `keyring.GetSecret` → **OS keychain / keychain-auth only**.
- `secrets set` / `secrets pull` **copy** plaintext into the keychain.
- No AWS SM, Vault, or 1Password adapter packages; `SecretResolver` is an in-process hook, not external backends.
- CLI has no `stores` command for federated health.

Conclusion: AgentSecrets is an excellent **delivery** product for secrets it stores. It is **not** a front-end to your existing sources of truth without copy-in.

## CLI scorecard vs planned `secret-broker` surface

| Command | AgentSecrets | ClauLock | Gap |
| --- | --- | --- | --- |
| `list` / `describe` | Yes (own keys) | Yes (own vault) | No multi-backend refs |
| `call` (HTTP inject) | Yes | Via shell rewrite | Single store |
| `run` (env inject) | `env` | `clsec-exec` | Single store |
| `policy` | Allowlist + secret policy | Local | Per-store federation missing |
| `audit` | `logs` | `clsec audit` | OK shape |
| `stores` | **Missing** | **Missing** | **Build** |
| `mcp` | Yes | Yes | Wrap broker, not a second policy path |
| `doctor` | `status` only | Partial | Adapter auth + leak self-check |

Adopting either tool stops the need for a new **vault**. It does **not** close the federated adapter gap.

## Path chosen

```text
Spike → federated live-read? → NO → build facade (CLI + MCP over one broker library)
```

`secret-broker` is a **facade, not a vault**. Adapters resolve from AWS / 1Password / Vault / env at use time. Secret bytes exist only inside the broker/wrapper process; never in MCP results, chat, audit, or errors.
