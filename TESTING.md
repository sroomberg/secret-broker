# Testing

How humans and agents should run tests for `secret-broker`. Prefer the **default** suite in CI and PRs; use **E2E** for full CLI/MCP paths; use **live E2E** only when real backends are configured.

## Security rules for all tests

- Never assert on or log real secret values.
- Prefer `memory` / `env` adapters and throwaway refs.
- Live backends must use **dedicated throwaway** secrets and deny-by-default allowlists.
- Do not commit credentials, `.env` files with values, or audit logs that contain plaintext.

## Quick start

```bash
pip install -e '.[dev,aws,vault]'

# Default: unit + local E2E (no cloud credentials)
pytest -q

# Explicit suites
pytest -q -m unit
pytest -q -m e2e
pytest -q -m "not e2e_live"   # what CI runs
```

## Test layers

| Layer | Marker | Needs network / cloud? | What it covers | Command |
| --- | --- | --- | --- | --- |
| **Unit** | `unit` (default for most files) | No | refs, redact, policy, broker mocks, harness file editors, hooks, docs presence | `pytest -m unit` |
| **E2E (local)** | `e2e` | Loopback / public httpbin optional | Full CLI + broker paths with `memory` adapter, harness install into temp `$HOME`, doctor leak-check | `pytest -m e2e` |
| **E2E (live)** | `e2e_live` | Yes — real AWS / `op` / Vault | Live-read adapters against throwaway secrets | `pytest -m e2e_live` (opt-in) |

Unmarked tests under `tests/` (outside `tests/e2e/`) are treated as **unit**. Everything under `tests/e2e/` is auto-marked `e2e` (and live modules also `e2e_live`).

## Layout

```text
tests/
  conftest.py              # markers + e2e auto-mark
  test_*.py                # unit / fast integration
  e2e/
    test_cli_e2e.py        # local end-to-end (always runnable)
    test_live_backends.py  # skipped unless SECRET_BROKER_E2E_LIVE=1
TESTING.md                 # this file
```

## Unit tests

```bash
pytest -q -m unit
# or by path
pytest -q tests/test_refs.py tests/test_broker.py tests/test_harness_plugins.py
```

Expectations:

- No GitHub / AWS / 1Password credentials required.
- Completes in seconds.
- Must stay green on every PR.

## E2E tests (local)

These drive the **installed CLI** and real `Broker` against temp config/policy/audit paths. They still never print secret bytes.

```bash
pip install -e '.[dev]'
pytest -q -m e2e
```

Covered scenarios (see `tests/e2e/test_cli_e2e.py`):

1. `secret-broker doctor` leak self-check passes.
2. `run` injects env and redacts child stdout.
3. `call` to an off-allowlist host is denied (exit code 2).
4. `harness install --all --scope project` writes Cursor / Claude / Codex / OpenCode configs under a temp root.
5. Audit log lines contain refs/destinations but not the fixture secret.

### Agent checklist (local E2E)

```text
1. pip install -e '.[dev]'
2. pytest -q -m e2e
3. Confirm exit 0
4. If failures: do not weaken redaction/policy assertions; fix product code
```

## E2E tests (live backends)

**Opt-in only.** Skipped in CI by default.

```bash
export SECRET_BROKER_E2E_LIVE=1
export SECRET_BROKER_CONFIG=/path/to/e2e-config.toml   # optional override

# AWS (default credential chain + region)
export SECRET_BROKER_E2E_AWS_REF='secret://aws/secret-broker-e2e#token'

# 1Password CLI must already be signed in
export SECRET_BROKER_E2E_OP_REF='secret://op/Employee/secret-broker-e2e/password'

# Vault
export VAULT_ADDR=https://vault.example:8200
export VAULT_TOKEN=…   # short-lived
export SECRET_BROKER_E2E_VAULT_REF='secret://vault/secret/secret-broker-e2e#token'

pip install -e '.[dev,aws,vault]'
pytest -q -m e2e_live
```

Example config fragment:

```toml
[broker]
audit_path = "/tmp/secret-broker-e2e-audit.jsonl"
policy_path = "/tmp/secret-broker-e2e-policy.toml"

[stores.aws]
type = "aws_secrets_manager"
region = "us-east-1"

[stores.op]
type = "onepassword"

[stores.vault]
type = "vault"
addr = "https://vault.example:8200"

[policy]
default_deny_hosts = true
allowed_hosts = ["httpbin.org", "example.com"]
allowed_bins = ["python3", "curl", "true"]
```

Live assertions must only check:

- HTTP status / deny reason / redaction markers
- That `describe` / `list` metadata has **no** secret-shaped substrings from the fixture

Never `assert value == …` on resolved plaintext in test output helpers.

## MCP / harness manual E2E

Automated coverage installs config files; a full agent-harness session is manual:

```bash
secret-broker harness install cursor --scope project
secret-broker harness install claude-code --scope project --hooks
# Restart Cursor / Claude Code, then prompt:
#   "List secrets via secret-broker MCP, then api_call https://example.com with ref …"
# Confirm: no plaintext in transcript; off-allowlist host denied.
```

## Lint + format (required with tests)

```bash
ruff check src tests
ruff format --check src tests
```

CI runs these before pytest (`docs/CI.md`).

## Selecting tests as an agent

| Goal | Command |
| --- | --- |
| Fast feedback while coding | `pytest -q -m unit --maxfail=1` |
| Before opening / updating a PR | `pytest -q -m "not e2e_live"` and `ruff check src tests` |
| Verify CLI contracts after CLI changes | `pytest -q -m e2e` |
| Verify AWS/op/Vault adapters | set live env vars → `pytest -q -m e2e_live` |
| Single file | `pytest -q tests/e2e/test_cli_e2e.py` |

## Failure triage

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Policy / redaction E2E fail | Regression in broker | Fix broker; do not delete the test |
| Harness E2E fail | Config path / merge bug | Fix `secret_broker/harness/*` |
| Live AWS skipped | `SECRET_BROKER_E2E_LIVE` unset or no ref | Expected in CI |
| Live AWS fail auth | Missing creds / IAM | Fix environment, not product allowlists |
| `doctor` leak_self_check FAIL | Redaction broken | Treat as P0 |

## Adding tests

1. **Unit** — put under `tests/test_*.py`; keep offline.
2. **Local E2E** — put under `tests/e2e/`, no `e2e_live` marker unless it needs real backends.
3. **Live E2E** — mark `@pytest.mark.e2e_live`, skip unless `SECRET_BROKER_E2E_LIVE=1`, read refs from env.
4. Update this file if you add a new layer or required env var.

TDD workflow: `docs/CONTRIBUTING.md`. Plans: `_plans/`.
