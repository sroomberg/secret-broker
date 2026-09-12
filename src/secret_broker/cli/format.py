"""Output helpers for CLI."""

from __future__ import annotations

import json
from typing import Any

import typer


def emit(data: Any, *, fmt: str, human_lines: list[str] | None = None) -> None:
    if fmt == "json":
        typer.echo(json.dumps(data, indent=2, default=str, sort_keys=True))
    else:
        if human_lines is None:
            typer.echo(json.dumps(data, indent=2, default=str, sort_keys=True))
        else:
            for line in human_lines:
                typer.echo(line)
