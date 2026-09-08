"""Pytest configuration: markers and E2E auto-marking."""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: fast offline unit tests")
    config.addinivalue_line("markers", "e2e: local end-to-end tests (CLI/broker, no cloud)")
    config.addinivalue_line(
        "markers",
        "e2e_live: live backend E2E (AWS/1Password/Vault); requires SECRET_BROKER_E2E_LIVE=1",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    e2e_root = Path(__file__).resolve().parent / "e2e"
    for item in items:
        path = Path(str(item.fspath)).resolve()
        try:
            path.relative_to(e2e_root)
            in_e2e = True
        except ValueError:
            in_e2e = False
        if in_e2e:
            item.add_marker(pytest.mark.e2e)
            if "live" in path.name:
                item.add_marker(pytest.mark.e2e_live)
        elif not any(m.name in {"unit", "e2e", "e2e_live"} for m in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
