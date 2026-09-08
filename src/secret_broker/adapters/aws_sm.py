"""AWS Secrets Manager adapter — live-read, no local copy."""

from __future__ import annotations

import json
from typing import Any

from secret_broker.adapters.base import AdapterError, SecretAdapter
from secret_broker.models import SecretMeta, StoreHealth, StoreStatus
from secret_broker.refs import SecretRef


class AwsSecretsManagerAdapter(SecretAdapter):
    backend = "aws_secrets_manager"

    def __init__(
        self,
        name: str = "aws",
        region: str | None = None,
        profile: str | None = None,
    ) -> None:
        self.name = name
        self.region = region
        self.profile = profile
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3
        except ImportError as exc:
            raise AdapterError(
                "boto3 not installed; pip install 'secret-broker[aws]'"
            ) from exc
        session_kwargs: dict[str, Any] = {}
        if self.profile:
            session_kwargs["profile_name"] = self.profile
        session = boto3.Session(**session_kwargs)
        self._client = session.client("secretsmanager", region_name=self.region)
        return self._client

    def health(self) -> StoreStatus:
        try:
            client = self._get_client()
            client.list_secrets(MaxResults=1)
            return StoreStatus(
                name=self.name,
                type=self.backend,
                health=StoreHealth.OK,
                detail=f"region={self.region or 'default'}",
            )
        except AdapterError as exc:
            return StoreStatus(
                name=self.name,
                type=self.backend,
                health=StoreHealth.UNAVAILABLE,
                detail=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 — map to health only
            return StoreStatus(
                name=self.name,
                type=self.backend,
                health=StoreHealth.UNAVAILABLE,
                detail=f"{type(exc).__name__}: auth or network failure",
            )

    def list_secrets(self) -> list[SecretMeta]:
        client = self._get_client()
        out: list[SecretMeta] = []
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"MaxResults": 100}
            if token:
                kwargs["NextToken"] = token
            resp = client.list_secrets(**kwargs)
            for item in resp.get("SecretList", []):
                sid = item["Name"]
                out.append(
                    SecretMeta(
                        name=sid,
                        ref=f"secret://{self.name}/{sid}",
                        store=self.name,
                        backend=self.backend,
                        description=item.get("Description"),
                        tags={t["Key"]: t.get("Value", "") for t in item.get("Tags", [])},
                    )
                )
            token = resp.get("NextToken")
            if not token:
                break
        return out

    def describe(self, ref: SecretRef) -> SecretMeta:
        client = self._get_client()
        try:
            resp = client.describe_secret(SecretId=ref.path)
        except Exception as exc:
            raise AdapterError(f"aws describe failed for {ref.display()}") from exc
        return SecretMeta(
            name=resp["Name"],
            ref=ref.display(),
            store=self.name,
            backend=self.backend,
            description=resp.get("Description"),
        )

    def resolve(self, ref: SecretRef) -> str:
        client = self._get_client()
        try:
            resp = client.get_secret_value(SecretId=ref.path)
        except Exception as exc:
            raise AdapterError(f"aws resolve failed for {ref.display()}") from exc
        if "SecretString" in resp:
            value = resp["SecretString"]
        else:
            raise AdapterError("binary secrets are not supported in v1")
        if ref.field:
            try:
                data = json.loads(value)
                if ref.field not in data:
                    raise AdapterError(f"json field not found in {ref.display()}")
                return str(data[ref.field])
            except json.JSONDecodeError as exc:
                raise AdapterError(f"secret is not JSON for {ref.display()}") from exc
        return value
