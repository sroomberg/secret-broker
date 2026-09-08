"""Parse and validate secret:// references."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote


class RefError(ValueError):
    """Invalid secret reference."""


@dataclass(frozen=True, slots=True)
class SecretRef:
    """A never-reveal reference to a secret in a configured store.

    Forms:
      secret://<store>/<path>[#<field>]
      secret://aws/my/secret#api_key
      secret://op/Personal/GitHub/credential
      secret://vault/secret/data/app#password
      secret://env/MY_TOKEN
    """

    store: str
    path: str
    field: str | None = None
    raw: str = ""

    def display(self) -> str:
        base = f"secret://{self.store}/{self.path}"
        if self.field:
            return f"{base}#{self.field}"
        return base


def parse_ref(value: str) -> SecretRef:
    raw = value.strip()
    if not raw:
        raise RefError("empty secret reference")
    if raw.startswith("secret://"):
        body = raw[len("secret://") :]
    elif "://" in raw:
        raise RefError(f"unsupported scheme in reference: {raw!r}")
    else:
        # Shorthand: store/path[#field]
        body = raw

    field: str | None = None
    if "#" in body:
        body, field = body.split("#", 1)
        field = unquote(field) or None

    body = body.lstrip("/")
    if "/" not in body:
        raise RefError(
            "reference must be secret://<store>/<path>[#field]; "
            f"got {value!r}"
        )
    store, path = body.split("/", 1)
    store = unquote(store).strip()
    path = unquote(path).strip().strip("/")
    if not store or not path:
        raise RefError(f"incomplete reference: {value!r}")
    return SecretRef(store=store, path=path, field=field, raw=raw)
