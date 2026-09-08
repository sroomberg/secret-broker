"""In-memory adapter for tests and doctor leak-check."""

from __future__ import annotations

from secret_broker.adapters.base import AdapterError, SecretAdapter
from secret_broker.models import SecretMeta, StoreHealth, StoreStatus
from secret_broker.refs import SecretRef


class MemoryAdapter(SecretAdapter):
    backend = "memory"

    def __init__(self, name: str = "memory", secrets: dict[str, str] | None = None) -> None:
        self.name = name
        self._secrets: dict[str, str] = dict(secrets or {})

    def put(self, key: str, value: str) -> None:
        self._secrets[key] = value

    def health(self) -> StoreStatus:
        return StoreStatus(
            name=self.name,
            type=self.backend,
            health=StoreHealth.OK,
            detail=f"{len(self._secrets)} in-memory entries",
        )

    def list_secrets(self) -> list[SecretMeta]:
        return [
            SecretMeta(
                name=k,
                ref=f"secret://{self.name}/{k}",
                store=self.name,
                backend=self.backend,
            )
            for k in sorted(self._secrets)
        ]

    def describe(self, ref: SecretRef) -> SecretMeta:
        if ref.path not in self._secrets:
            raise AdapterError(f"secret not found: {ref.display()}")
        return SecretMeta(
            name=ref.path,
            ref=ref.display(),
            store=self.name,
            backend=self.backend,
        )

    def resolve(self, ref: SecretRef) -> str:
        try:
            return self._secrets[ref.path]
        except KeyError as exc:
            raise AdapterError(f"secret not found: {ref.display()}") from exc
