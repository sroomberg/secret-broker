"""Load broker configuration (TOML)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


DEFAULT_CONFIG_CANDIDATES = (
    "SECRET_BROKER_CONFIG",
    "~/.config/secret-broker/config.toml",
    "./secret-broker.toml",
)


@dataclass
class BrokerConfig:
    path: Path | None = None
    default_format: str = "table"
    audit_path: str = "~/.local/state/secret-broker/audit.jsonl"
    policy_path: str = "~/.config/secret-broker/policy.toml"
    stores: dict[str, dict[str, Any]] = field(default_factory=dict)
    policy_bootstrap: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def find_config_path(explicit: str | None = None) -> Path | None:
    if explicit:
        return Path(os.path.expanduser(explicit))
    env = os.environ.get("SECRET_BROKER_CONFIG")
    if env:
        return Path(os.path.expanduser(env))
    for candidate in ("~/.config/secret-broker/config.toml", "./secret-broker.toml"):
        p = Path(os.path.expanduser(candidate))
        if p.exists():
            return p
    return None


def load_config(explicit: str | None = None) -> BrokerConfig:
    path = find_config_path(explicit)
    if path is None or not path.exists():
        # Sensible defaults for tests / doctor without a file
        return BrokerConfig(
            stores={
                "env": {"type": "env"},
                "memory": {"type": "memory"},
            },
            policy_bootstrap={
                "default_deny_hosts": True,
                "allowed_hosts": ["httpbin.org", "example.com"],
                "allowed_bins": ["curl", "echo", "true", "false", "env", "printenv"],
            },
        )

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    broker = data.get("broker", {})
    stores = data.get("stores", {})
    # Normalize: allow [stores.name] tables
    return BrokerConfig(
        path=path,
        default_format=broker.get("default_format", "table"),
        audit_path=broker.get("audit_path", "~/.local/state/secret-broker/audit.jsonl"),
        policy_path=broker.get("policy_path", "~/.config/secret-broker/policy.toml"),
        stores=dict(stores),
        policy_bootstrap=dict(data.get("policy", {})),
        raw=data,
    )
