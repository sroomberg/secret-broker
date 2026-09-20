# GitHub Actions

## Workflows

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| [`ci.yml`](../.github/workflows/ci.yml) | push / PR | Ruff, pytest on 3.11–3.13, build + wheel smoke, harness plugin zips |
| [`publish.yml`](../.github/workflows/publish.yml) | `v*` tag push / manual | PyPI Trusted Publishing + attach `secret-broker-plugin-*.zip` to GitHub Releases when used |

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

1. Bump `version` in `pyproject.toml` and `src/secret_broker/__init__.py` (keep them in sync).
2. Merge to `master`.
3. Tag and push (e.g. `git tag v0.1.1 && git push origin v0.1.1`). The **Publish** workflow uploads to PyPI.
4. Or run **Actions → Publish → Run workflow** and choose `testpypi` / `pypi`.

### Next tag after history rewrite (2026-09-20)

`v0.1.0` is already on PyPI from the first publish. A force-push that moved the `v0.1.0` tag re-triggered **Publish** and failed with `400 File already exists` for `secret_broker-0.1.0-*`. Do **not** re-use `v0.1.0`. After merging the `0.1.1` version bump, cut **`v0.1.1`** on `master` to publish the new release.

## Local parity

```bash
pip install -e '.[dev,aws,vault]'
ruff check src tests
ruff format --check src tests
pytest -q -m "not e2e_live"
python -m build && twine check dist/*
```
