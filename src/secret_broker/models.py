"""Shared models — never include secret values."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StoreHealth(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class SecretMeta(BaseModel):
    """Metadata about a secret — never the value."""

    name: str
    ref: str
    store: str
    backend: str
    description: str | None = None
    allowed_ops: list[str] = Field(default_factory=lambda: ["call", "run"])
    tags: dict[str, str] = Field(default_factory=dict)


class StoreStatus(BaseModel):
    name: str
    type: str
    health: StoreHealth
    detail: str = ""


class AuditEvent(BaseModel):
    """Audit record. Intentionally has no value field."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str = "cli"
    op: str
    ref: str
    destination: str = ""
    status: str = "ok"
    reason: str = ""
    duration_ms: int = 0
    meta: dict[str, Any] = Field(default_factory=dict)


class CallResult(BaseModel):
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    body: str
    redacted: bool = False
    duration_ms: int = 0


class RunResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    redacted: bool = False
    duration_ms: int = 0
