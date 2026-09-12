"""TDD: CI/CD workflow files must exist and stay well-formed."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_ci_and_publish_workflows_exist():
    assert (WORKFLOWS / "ci.yml").is_file()
    assert (WORKFLOWS / "publish.yml").is_file()
    assert (ROOT / ".github" / "dependabot.yml").is_file()


@pytest.mark.parametrize("name", ["ci.yml", "publish.yml"])
def test_workflow_yaml_parses(name: str):
    # PyYAML turns the key `on:` into boolean True
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "jobs" in data
    assert data["jobs"], f"{name} has no jobs"
    assert True in data or "on" in data


def test_testing_guide_documents_e2e_commands():
    text = (ROOT / "TESTING.md").read_text(encoding="utf-8")
    assert "pytest -q -m e2e" in text
    assert "SECRET_BROKER_E2E_LIVE" in text
    assert "Never assert on or log real secret values" in text


def test_ci_covers_python_matrix_and_plugins():
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    for version in ("3.11", "3.12", "3.13"):
        assert version in text
    assert "ruff check" in text
    assert "pytest" in text
    assert "not e2e_live" in text
    assert "python -m build" in text
    assert "harness package" in text
    assert "list_artifact_ids" in text


def test_publish_uses_trusted_publishing():
    text = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert "id-token: write" in text
    assert "pypa/gh-action-pypi-publish" in text
    assert "environment:" in text
    assert "PYPI_API_TOKEN" not in text
    assert "password:" not in text
    assert '"v*"' in text
    assert "workflow_dispatch:" in text


def test_publish_packages_plugin_zips():
    text = (WORKFLOWS / "publish.yml").read_text(encoding="utf-8")
    assert "harness package" in text
    assert "harness-plugin-zips" in text
