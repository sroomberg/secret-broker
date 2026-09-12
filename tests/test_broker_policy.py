"""TDD: additional broker policy / SSRF / describe gaps."""

from __future__ import annotations

from pathlib import Path

import pytest

from secret_broker.adapters.memory import MemoryAdapter
from secret_broker.audit import AuditLog
from secret_broker.broker import Broker
from secret_broker.config import BrokerConfig
from secret_broker.policy import Policy, PolicyDenied


@pytest.fixture
def broker(tmp_path: Path) -> Broker:
    mem = MemoryAdapter()
    mem.put("TOKEN", "val")
    return Broker(
        config=BrokerConfig(
            audit_path=str(tmp_path / "a.jsonl"),
            policy_path=str(tmp_path / "p.toml"),
        ),
        adapters={"memory": mem},
        policy=Policy(
            default_deny_hosts=True,
            allowed_hosts={"example.com"},
            allowed_bins={"python3"},
        ),
        audit=AuditLog(tmp_path / "a.jsonl"),
    )


def test_policy_persist_roundtrip(broker: Broker, tmp_path: Path):
    broker.policy_allow_host("api.github.com")
    broker.policy_allow_bin("curl")
    text = Path(broker.config.policy_path).read_text(encoding="utf-8")
    assert "api.github.com" in text
    assert "curl" in text
    # reload
    from secret_broker.policy import load_policy

    loaded = load_policy(broker.config.policy_path)
    assert "api.github.com" in loaded.allowed_hosts
    assert "curl" in loaded.allowed_bins


def test_header_inject_requires_name(broker: Broker):
    broker.policy.allow_host("example.com")
    with pytest.raises(ValueError, match="header"):
        broker.call(
            url="https://example.com/",
            ref_str="secret://memory/TOKEN",
            inject="header",
        )


def test_ssrf_blocks_metadata_ip(broker: Broker):
    broker.policy.allow_host("169.254.169.254")
    with pytest.raises(PolicyDenied, match="SSRF"):
        broker.call(
            url="http://169.254.169.254/latest/meta-data/",
            ref_str="secret://memory/TOKEN",
        )
