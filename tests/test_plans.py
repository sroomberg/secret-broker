"""Plans directory is part of the source tree."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANS = ROOT / "_plans"


def test_plans_directory_has_indexed_documents():
    assert (PLANS / "README.md").is_file()
    expected = [
        "001-secret-broker-architecture.md",
        "002-try-existing-tools-first.md",
        "003-federated-facade.md",
        "004-harness-plugins-tdd.md",
        "005-github-actions.md",
        "006-testing-guide.md",
        "007-harness-plugin-publishing.md",
    ]
    for name in expected:
        path = PLANS / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert text.lstrip().startswith("#"), name
        assert "**Status:**" in text
