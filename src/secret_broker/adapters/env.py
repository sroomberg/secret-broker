"""Resolve secrets from the broker process environment (demo / CI)."""

from __future__ import annotations

import os

from secret_broker.adapters.base import AdapterError, SecretAdapter
from secret_broker.models import SecretMeta, StoreHealth, StoreStatus
from secret_broker.refs import SecretRef


class EnvAdapter(SecretAdapter):
    backend = "env"

    def __init__(self, name: str = "env", prefix: str = "") -> None:
        self.name = name
        self.prefix = prefix

    def _env_key(self, path: str) -> str:
        return f"{self.prefix}{path}"

    def health(self) -> StoreStatus:
        return StoreStatus(
            name=self.name,
            type=self.backend,
            health=StoreHealth.OK,
            detail="reads process environment",
        )

    def list_secrets(self) -> list[SecretMeta]:
        # Only list prefixed keys if prefix set; otherwise do not dump entire env.
        if not self.prefix:
            return []
        out: list[SecretMeta] = []
        for key in sorted(os.environ):
            if key.startswith(self.prefix):
                name = key[len(self.prefix) :]
                out.append(
                    SecretMeta(
                        name=name,
                        ref=f"secret://{self.name}/{name}",
                        store=self.name,
                        backend=self.backend,
                    )
                )
        return out

    def describe(self, ref: SecretRef) -> SecretMeta:
        key = self._env_key(ref.path)
        if key not in os.environ:
            raise AdapterError(f"env var not set: {ref.display()}")
        return SecretMeta(
            name=ref.path,
            ref=ref.display(),
            store=self.name,
            backend=self.backend,
        )

    def resolve(self, ref: SecretRef) -> str:
        key = self._env_key(ref.path)
        try:
            return os.environ[key]
        except KeyError as exc:
            raise AdapterError(f"env var not set: {ref.display()}") from exc
