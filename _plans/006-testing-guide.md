# Plan: Structured testing guide + E2E suites

**Status:** implemented

## Goal

Give humans and agents a single `TESTING.md` that explains how to run unit, local E2E, and live-backend E2E tests without leaking secrets.

## Deliverables

- [x] Root `TESTING.md` with layers, commands, env vars, failure triage
- [x] Pytest markers: `unit`, `e2e`, `e2e_live` (+ auto-mark via `tests/conftest.py`)
- [x] `tests/e2e/` local CLI/broker E2E (no cloud)
- [x] `tests/e2e/test_live_backends.py` skipped unless `SECRET_BROKER_E2E_LIVE=1`
- [x] CI runs `pytest -m "not e2e_live"`
