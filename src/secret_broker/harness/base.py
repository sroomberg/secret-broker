"""Agent harness plugin protocol and shared models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

SERVER_NAME = "secret-broker"


class Scope(StrEnum):
    USER = "user"
    PROJECT = "project"


class HarnessStatus(BaseModel):
    harness: str
    installed: bool
    scope: Scope
    mcp: bool = False
    hooks: bool = False
    paths: list[str] = Field(default_factory=list)
    detail: str = ""


class InstallResult(BaseModel):
    harness: str
    scope: Scope
    paths_touched: list[str] = Field(default_factory=list)
    mcp_installed: bool = False
    hooks_installed: bool = False
    detail: str = ""


class HarnessPlugin(ABC):
    """Install MCP (+ optional hooks) into an agent harness config."""

    id: str
    name: str
    supports_mcp: bool = True
    supports_hooks: bool = False

    @abstractmethod
    def status(self, *, scope: Scope, root: Path, home: Path) -> HarnessStatus:
        raise NotImplementedError

    @abstractmethod
    def install(
        self,
        *,
        scope: Scope,
        root: Path,
        home: Path,
        broker_command: list[str],
        config_path: str | None,
        with_hooks: bool,
    ) -> InstallResult:
        raise NotImplementedError

    @abstractmethod
    def uninstall(self, *, scope: Scope, root: Path, home: Path) -> InstallResult:
        raise NotImplementedError
