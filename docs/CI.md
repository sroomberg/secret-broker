# GitHub Actions

## Workflows

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| [`ci.yml`](../.github/workflows/ci.yml) | push / PR | Ruff, pytest on 3.11–3.13, build + wheel smoke test |
| [`publish.yml`](../.github/workflows/publish.yml) | GitHub Release / manual | Build artifacts; publish to TestPyPI or PyPI via **Trusted Publishing** (OIDC) |

## One-time PyPI setup (Trusted Publishing)

No long-lived `PYPI_API_TOKEN` is required.

1. Create the project on [PyPI](https://pypi.org/) (or publish once via TestPyPI first).
2. In PyPI → project → **Publishing** → **Add a new pending publisher**:
   - Owner: `sroomberg`
   - Repository: `secret-broker`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. Repeat for TestPyPI with environment `testpypi`.
4. In GitHub → **Settings → Environments**:
   - Create `pypi` (recommended: required reviewers)
   - Create `testpypi`

## Releasing

1. Bump `version` in `pyproject.toml`.
2. Merge to `master`.
3. Create a GitHub Release (tag e.g. `v0.1.0`). The **Publish** workflow uploads to PyPI.
4. Or run **Actions → Publish → Run workflow** and choose `testpypi` / `pypi`.

## Local parity

```bash
pip install -e '.[dev,aws,vault]'
ruff check src tests
ruff format --check src tests
pytest -q
python -m build && twine check dist/*
```
