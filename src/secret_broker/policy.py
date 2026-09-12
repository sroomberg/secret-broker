"""Per-secret and global allowlists. Destination allowlist is mandatory for call/run."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


class PolicyDenied(PermissionError):
    """Destination or binary not allowed for this secret."""


@dataclass
class Policy:
    default_deny_hosts: bool = True
    allowed_hosts: set[str] = field(default_factory=set)
    allowed_bins: set[str] = field(default_factory=set)
    # ref display string -> extra allowlists
    per_ref_hosts: dict[str, set[str]] = field(default_factory=dict)
    per_ref_bins: dict[str, set[str]] = field(default_factory=dict)

    def hosts_for(self, ref: str) -> set[str]:
        return set(self.allowed_hosts) | self.per_ref_hosts.get(ref, set())

    def bins_for(self, ref: str) -> set[str]:
        return set(self.allowed_bins) | self.per_ref_bins.get(ref, set())

    def check_host(self, ref: str, url: str) -> None:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            raise PolicyDenied("URL has no hostname")
        allowed = {h.lower() for h in self.hosts_for(ref)}
        if self.default_deny_hosts:
            if host not in allowed and not _host_matches(host, allowed):
                raise PolicyDenied(f"host not allowed: {host}")
        elif allowed and host not in allowed and not _host_matches(host, allowed):
            raise PolicyDenied(f"host not allowed: {host}")

    def check_bin(self, ref: str, command: list[str]) -> None:
        if not command:
            raise PolicyDenied("empty command")
        binary = Path(command[0]).name
        allowed = self.bins_for(ref)
        if allowed and binary not in allowed:
            raise PolicyDenied(f"binary not allowed: {binary}")

    def allow_host(self, host: str, ref: str | None = None) -> None:
        host = host.lower().strip()
        if ref:
            self.per_ref_hosts.setdefault(ref, set()).add(host)
        else:
            self.allowed_hosts.add(host)

    def allow_bin(self, binary: str, ref: str | None = None) -> None:
        binary = Path(binary).name
        if ref:
            self.per_ref_bins.setdefault(ref, set()).add(binary)
        else:
            self.allowed_bins.add(binary)

    def as_dict(self) -> dict[str, Any]:
        return {
            "default_deny_hosts": self.default_deny_hosts,
            "allowed_hosts": sorted(self.allowed_hosts),
            "allowed_bins": sorted(self.allowed_bins),
            "per_ref_hosts": {k: sorted(v) for k, v in sorted(self.per_ref_hosts.items())},
            "per_ref_bins": {k: sorted(v) for k, v in sorted(self.per_ref_bins.items())},
        }


def _host_matches(host: str, allowed: set[str]) -> bool:
    # Exact match only by default (no wildcard subdomain leakage).
    return host in allowed


def load_policy(path: str | Path | None, bootstrap: dict[str, Any] | None = None) -> Policy:
    policy = Policy()
    if bootstrap:
        policy.default_deny_hosts = bool(bootstrap.get("default_deny_hosts", True))
        policy.allowed_hosts = {h.lower() for h in bootstrap.get("allowed_hosts", [])}
        policy.allowed_bins = set(bootstrap.get("allowed_bins", []))

    if not path:
        return policy
    p = Path(os.path.expanduser(str(path)))
    if not p.exists():
        return policy
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    root = data.get("policy", data)
    if "default_deny_hosts" in root:
        policy.default_deny_hosts = bool(root["default_deny_hosts"])
    policy.allowed_hosts |= {h.lower() for h in root.get("allowed_hosts", [])}
    policy.allowed_bins |= set(root.get("allowed_bins", []))
    for ref, cfg in root.get("refs", {}).items():
        if "allowed_hosts" in cfg:
            policy.per_ref_hosts[ref] = {h.lower() for h in cfg["allowed_hosts"]}
        if "allowed_bins" in cfg:
            policy.per_ref_bins[ref] = set(cfg["allowed_bins"])
    return policy


def save_policy(path: str | Path, policy: Policy) -> None:
    p = Path(os.path.expanduser(str(path)))
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# secret-broker policy — destinations only; never secret values",
        "[policy]",
        f"default_deny_hosts = {str(policy.default_deny_hosts).lower()}",
        f"allowed_hosts = {_toml_list(sorted(policy.allowed_hosts))}",
        f"allowed_bins = {_toml_list(sorted(policy.allowed_bins))}",
        "",
    ]
    for ref, hosts in sorted(policy.per_ref_hosts.items()):
        lines.append(f'[policy.refs."{ref}"]')
        lines.append(f"allowed_hosts = {_toml_list(sorted(hosts))}")
        bins = policy.per_ref_bins.get(ref, set())
        if bins:
            lines.append(f"allowed_bins = {_toml_list(sorted(bins))}")
        lines.append("")
    for ref, bins in sorted(policy.per_ref_bins.items()):
        if ref in policy.per_ref_hosts:
            continue
        lines.append(f'[policy.refs."{ref}"]')
        lines.append(f"allowed_bins = {_toml_list(sorted(bins))}")
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _toml_list(items: list[str]) -> str:
    return "[" + ", ".join(f'"{i}"' for i in items) + "]"
