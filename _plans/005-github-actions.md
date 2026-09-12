# Plan: GitHub Actions (test + publish)

**Status:** implemented  
**Depends on:** package layout in `003`

## Goal

Automate quality gates and releases without long-lived PyPI tokens.

## CI (`.github/workflows/ci.yml`)

Triggers: push (incl. `cursor/**`), pull_request, workflow_dispatch.

Jobs:

1. **lint** — `ruff check`, `ruff format --check`
2. **test** — matrix Python **3.11 / 3.12 / 3.13**; `pip install -e ".[dev,aws,vault]"`; `pytest`
3. **build** — `python -m build`, `twine check`, smoke-install wheel (`secret-broker version`, `harness list`), upload `dist/` artifact

Permissions: `contents: read`. Concurrency cancels in-progress runs on the same ref.

## Publish (`.github/workflows/publish.yml`)

Triggers:

- GitHub Release `published` → PyPI
- `workflow_dispatch` with target `testpypi` | `pypi`

Pattern: build job → artifact → publish job with:

- `permissions: id-token: write`
- GitHub Environment `pypi` / `testpypi`
- `pypa/gh-action-pypi-publish@release/v1`
- **No** `PYPI_API_TOKEN` / password

## Dependabot

Weekly updates for `github-actions` and `pip`.

## One-time human setup

1. Create GitHub Environments `pypi` (required reviewers recommended) and `testpypi`.
2. Configure PyPI + TestPyPI Trusted Publishers:
   - Owner `sroomberg`, repo `secret-broker`, workflow `publish.yml`, matching environment name.
3. Release flow: bump `pyproject.toml` version → merge → GitHub Release tag → publish workflow.

## Acceptance

- [x] Workflows present and covered by `tests/test_github_actions.py`
- [x] Publish workflow textually forbids API-token style secrets
- [x] Docs in `docs/CI.md` + README badge / pointer
