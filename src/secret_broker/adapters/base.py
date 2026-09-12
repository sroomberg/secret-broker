"""Adapter protocol — resolve secret bytes only inside the broker process."""

from __future__ import annotations

from abc import ABC, abstractmethod

from secret_broker.models import SecretMeta, StoreStatus
from secret_broker.refs import SecretRef


class AdapterError(RuntimeError):
    """Adapter failure. Message must never include secret bytes."""


class SecretAdapter(ABC):
    name: str
    backend: str

    @abstractmethod
    def health(self) -> StoreStatus:
        raise NotImplementedError

    @abstractmethod
    def list_secrets(self) -> list[SecretMeta]:
        """Return names/metadata only — never values."""

    @abstractmethod
    def describe(self, ref: SecretRef) -> SecretMeta:
        raise NotImplementedError

    @abstractmethod
    def resolve(self, ref: SecretRef) -> str:
        """Return plaintext for injection only. Caller must not log/return it."""
