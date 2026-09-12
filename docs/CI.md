# GitHub Actions

## Workflows

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| [`ci.yml`](../.github/workflows/ci.yml) | push / PR | Ruff, pytest on 3.11–3.13, build + wheel smoke, harness plugin zips |
| [`publish.yml`](../.github/workflows/publish.yml) | GitHub Release / manual | PyPI publish (OIDC or optional token) + attach `secret-broker-plugin-*.zip` to the Release |

## One-time PyPI setup

Publishing uses [`pypa/gh-action-pypi-publish`](https://github.com/pypa/gh-action-pypi-publish) with the GitHub Environment `pypi`. **Trusted Publishing (OIDC) is preferred**; an optional API token works until OIDC is configured.

### Trusted Publishing (recommended)

1. Create the project on [PyPI](https://pypi.org/) (or publish once via TestPyPI first).
2. In PyPI → project → **Publishing** → **Add a new pending publisher**:
   - **Owner:** `sroomberg`
   - **Repository name:** `secret-broker`
   - **Workflow filename:** `publish.yml`
   - **Environment name:** `pypi`
3. Repeat on [TestPyPI](https://test.pypi.org/) with environment `testpypi`.
4. In GitHub → **Settings → Environments**, create:
   - `pypi` (recommended: required reviewers)
   - `testpypi`

When `PYPI_API_TOKEN` / `TESTPYPI_API_TOKEN` are unset, the publish jobs use OIDC (`permissions: id-token: write` on the publish job).

### Optional API token fallback

Use this for a first publish before Trusted Publishing is live, or if you prefer a token:

1. Create a **project-scoped** API token on PyPI (or TestPyPI).
2. Add secrets on the matching GitHub Environment (not in this repo):
   - `PYPI_API_TOKEN` on environment `pypi`
   - `TESTPYPI_API_TOKEN` on environment `testpypi`

If a secret is set, the workflow uses it; if empty or absent, it falls back to OIDC.

## Releasing

1. Bump `version` in `pyproject.toml`.
2. Merge to `master`.
3. Create a GitHub Release (tag e.g. `v0.1.0`). The **Publish** workflow uploads to PyPI.
4. Or run **Actions → Publish → Run workflow** and choose `testpypi` / `pypi`.

Publishing does **not** run on push to `master` — only on published Releases or manual dispatch.

## Local parity

```bash
pip install -e '.[dev,aws,vault]'
ruff check src tests
ruff format --check src tests
pytest -q -m "not e2e_live"
python -m build && twine check dist/*
```
