"""HashiCorp Vault KV adapter — live-read, no local copy."""

from __future__ import annotations

import os
from typing import Any

from secret_broker.adapters.base import AdapterError, SecretAdapter
from secret_broker.models import SecretMeta, StoreHealth, StoreStatus
from secret_broker.refs import SecretRef


class VaultAdapter(SecretAdapter):
    backend = "vault"

    def __init__(
        self,
        name: str = "vault",
        addr: str | None = None,
        token_env: str = "VAULT_TOKEN",
        mount: str = "secret",
        kv_version: int = 2,
    ) -> None:
        self.name = name
        self.addr = addr or os.environ.get("VAULT_ADDR")
        self.token_env = token_env
        self.mount = mount
        self.kv_version = kv_version
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import hvac
        except ImportError as exc:
            raise AdapterError("hvac not installed; pip install 'secret-broker[vault]'") from exc
        if not self.addr:
            raise AdapterError("vault addr not configured (addr or VAULT_ADDR)")
        token = os.environ.get(self.token_env)
        if not token:
            raise AdapterError(f"vault token env {self.token_env} not set")
        client = hvac.Client(url=self.addr, token=token)
        self._client = client
        return client

    def health(self) -> StoreStatus:
        try:
            client = self._get_client()
            ok = bool(client.is_authenticated())
            return StoreStatus(
                name=self.name,
                type=self.backend,
                health=StoreHealth.OK if ok else StoreHealth.UNAVAILABLE,
                detail=f"addr={self.addr} authenticated={ok}",
            )
        except AdapterError as exc:
            return StoreStatus(
                name=self.name,
                type=self.backend,
                health=StoreHealth.UNAVAILABLE,
                detail=str(exc),
            )
        except Exception:  # noqa: BLE001
            return StoreStatus(
                name=self.name,
                type=self.backend,
                health=StoreHealth.UNAVAILABLE,
                detail="vault health check failed",
            )

    def list_secrets(self) -> list[SecretMeta]:
        # Listing KV recursively is mount-specific; keep v1 conservative.
        client = self._get_client()
        try:
            if self.kv_version == 2:
                listing = client.secrets.kv.v2.list_secrets(path="", mount_point=self.mount)
            else:
                listing = client.secrets.kv.v1.list_secrets(path="", mount_point=self.mount)
        except Exception as exc:
            raise AdapterError("vault list failed") from exc
        keys = (listing or {}).get("data", {}).get("keys", [])
        return [
            SecretMeta(
                name=k.rstrip("/"),
                ref=f"secret://{self.name}/{self.mount}/{k.rstrip('/')}",
                store=self.name,
                backend=self.backend,
            )
            for k in keys
            if not str(k).endswith("/")
        ]

    def describe(self, ref: SecretRef) -> SecretMeta:
        mount, path = self._parse(ref)
        return SecretMeta(
            name=f"{mount}/{path}",
            ref=ref.display(),
            store=self.name,
            backend=self.backend,
            description=f"field={ref.field}" if ref.field else None,
        )

    def resolve(self, ref: SecretRef) -> str:
        client = self._get_client()
        mount, path = self._parse(ref)
        try:
            if self.kv_version == 2:
                resp = client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount)
                data = resp["data"]["data"]
            else:
                resp = client.secrets.kv.v1.read_secret(path=path, mount_point=mount)
                data = resp["data"]
        except Exception as exc:
            raise AdapterError(f"vault resolve failed for {ref.display()}") from exc
        if ref.field:
            if ref.field not in data:
                raise AdapterError(f"field not found in {ref.display()}")
            return str(data[ref.field])
        if len(data) == 1:
            return str(next(iter(data.values())))
        raise AdapterError(f"ambiguous vault secret; specify #field for {ref.display()}")

    def _parse(self, ref: SecretRef) -> tuple[str, str]:
        parts = ref.path.split("/", 1)
        if len(parts) == 1:
            return self.mount, parts[0]
        return parts[0], parts[1]
