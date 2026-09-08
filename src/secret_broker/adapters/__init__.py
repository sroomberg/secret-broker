"""Secret store adapters."""

from __future__ import annotations

from typing import Any

from secret_broker.adapters.base import AdapterError, SecretAdapter

__all__ = [
    "AdapterError",
    "SecretAdapter",
    "build_adapters",
]


def build_adapters(stores: dict[str, dict[str, Any]]) -> dict[str, SecretAdapter]:
    from secret_broker.adapters.aws_sm import AwsSecretsManagerAdapter
    from secret_broker.adapters.env import EnvAdapter
    from secret_broker.adapters.memory import MemoryAdapter
    from secret_broker.adapters.onepassword import OnePasswordAdapter
    from secret_broker.adapters.vault import VaultAdapter

    registry: dict[str, type[SecretAdapter]] = {
        "env": EnvAdapter,
        "memory": MemoryAdapter,
        "aws_secrets_manager": AwsSecretsManagerAdapter,
        "aws": AwsSecretsManagerAdapter,
        "onepassword": OnePasswordAdapter,
        "op": OnePasswordAdapter,
        "vault": VaultAdapter,
    }

    adapters: dict[str, SecretAdapter] = {}
    for name, cfg in stores.items():
        cfg = dict(cfg)
        typ = cfg.pop("type", name)
        cls = registry.get(typ)
        if cls is None:
            raise AdapterError(f"unknown store type: {typ!r} (store {name!r})")
        adapters[name] = cls(name=name, **cfg)  # type: ignore[call-arg]
    return adapters
