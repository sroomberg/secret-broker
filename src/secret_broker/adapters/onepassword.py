"""1Password adapter via `op` CLI — live-read, no local copy."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from secret_broker.adapters.base import AdapterError, SecretAdapter
from secret_broker.models import SecretMeta, StoreHealth, StoreStatus
from secret_broker.refs import SecretRef


class OnePasswordAdapter(SecretAdapter):
    backend = "onepassword"

    def __init__(self, name: str = "op", account: str | None = None) -> None:
        self.name = name
        self.account = account

    def _op(self, args: list[str], *, timeout: float = 60.0) -> str:
        if not shutil.which("op"):
            raise AdapterError("1Password CLI `op` not found on PATH")
        cmd = ["op", *args]
        if self.account:
            cmd.extend(["--account", self.account])
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterError("op timed out") from exc
        if proc.returncode != 0:
            # Do not forward stderr verbatim — may contain sensitive hints
            raise AdapterError(f"op failed (exit {proc.returncode})")
        return proc.stdout

    def health(self) -> StoreStatus:
        try:
            self._op(["whoami"], timeout=15.0)
            return StoreStatus(
                name=self.name,
                type=self.backend,
                health=StoreHealth.OK,
                detail="op authenticated",
            )
        except AdapterError as exc:
            return StoreStatus(
                name=self.name,
                type=self.backend,
                health=StoreHealth.UNAVAILABLE,
                detail=str(exc),
            )

    def list_secrets(self) -> list[SecretMeta]:
        raw = self._op(["item", "list", "--format", "json"])
        items: list[dict[str, Any]] = json.loads(raw) if raw.strip() else []
        out: list[SecretMeta] = []
        for item in items:
            vault = (item.get("vault") or {}).get("name") or "unknown"
            title = item.get("title") or item.get("id")
            out.append(
                SecretMeta(
                    name=f"{vault}/{title}",
                    ref=f"secret://{self.name}/{vault}/{title}",
                    store=self.name,
                    backend=self.backend,
                    tags={"category": str(item.get("category", ""))},
                )
            )
        return out

    def describe(self, ref: SecretRef) -> SecretMeta:
        vault, item, _field = self._parse_path(ref)
        return SecretMeta(
            name=f"{vault}/{item}",
            ref=ref.display(),
            store=self.name,
            backend=self.backend,
            description=f"field={_field}" if _field else None,
        )

    def resolve(self, ref: SecretRef) -> str:
        vault, item, field = self._parse_path(ref)
        # Prefer structured read; field defaults to password/credential
        if field:
            reference = f"op://{vault}/{item}/{field}"
            return self._op(["read", reference]).rstrip("\n")
        # Try password then credential
        for candidate in ("password", "credential", "token"):
            try:
                return self._op(["read", f"op://{vault}/{item}/{candidate}"]).rstrip("\n")
            except AdapterError:
                continue
        raise AdapterError(f"could not resolve field for {ref.display()}")

    def _parse_path(self, ref: SecretRef) -> tuple[str, str, str | None]:
        parts = ref.path.split("/")
        if len(parts) < 2:
            raise AdapterError("op refs must be secret://op/<vault>/<item>[/<field>] or #field")
        vault, item = parts[0], parts[1]
        field = ref.field
        if len(parts) >= 3 and not field:
            field = "/".join(parts[2:])
        return vault, item, field
