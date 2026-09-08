"""Append-only JSONL audit log — no secret values."""

from __future__ import annotations

import json
import os
from pathlib import Path

from secret_broker.models import AuditEvent


class AuditLog:
    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(os.path.expanduser(str(path))) if path else None

    def record(self, event: AuditEvent) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Exclude any accidental value-like keys
        payload = event.model_dump(mode="json")
        payload.pop("value", None)
        payload.get("meta", {}).pop("value", None)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")

    def read(self, limit: int = 100) -> list[AuditEvent]:
        if not self.path or not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        events: list[AuditEvent] = []
        for line in lines[-limit:]:
            if not line.strip():
                continue
            events.append(AuditEvent.model_validate(json.loads(line)))
        return events
