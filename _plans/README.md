# Plans index

Design and execution plans for `secret-broker`, checked into source so agents and humans share the same history.

| Plan | Status | Summary |
| --- | --- | --- |
| [`001-secret-broker-architecture.md`](001-secret-broker-architecture.md) | accepted | Agents get references; trusted process uses secrets; CLI + MCP equal surfaces |
| [`002-try-existing-tools-first.md`](002-try-existing-tools-first.md) | done (spike) | Prefer ClauLock / AgentSecrets / wrappers before building a vault |
| [`003-federated-facade.md`](003-federated-facade.md) | implemented | Build facade over AWS / 1Password / Vault after spike showed no federation |
| [`004-harness-plugins-tdd.md`](004-harness-plugins-tdd.md) | implemented | TDD plugins for Cursor, Claude Code, Codex, OpenCode, Continue |
| [`005-github-actions.md`](005-github-actions.md) | implemented | CI matrix + Trusted Publishing to PyPI |
| [`006-testing-guide.md`](006-testing-guide.md) | implemented | Structured TESTING.md + local/live E2E markers |

Related living docs (not plans): `SPIKE.md`, `docs/HARNESSES.md`, `docs/CI.md`, `docs/CONTRIBUTING.md`.

Keep new design write-ups here as numbered `NNN-slug.md` files and link them from this index.
