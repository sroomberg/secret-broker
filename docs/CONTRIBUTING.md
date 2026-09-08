# Contributing

## TDD

1. Write a failing test under `tests/` (RED).
2. Implement the smallest change in `src/secret_broker/` (GREEN).
3. Refactor; keep `pytest -q -m "not e2e_live"` and `ruff check src tests` clean.

Do not add `get` / `reveal` / `cat` APIs that return secret bytes.

How to run unit / E2E / live suites: see [`TESTING.md`](../TESTING.md).

## Harness plugins

See `docs/HARNESSES.md`. New agent products get a `HarnessPlugin` implementation + registry entry + path markers in `tests/test_harness_plugins.py`.
