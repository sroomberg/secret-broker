"""MCP server — thin wrapper over Broker (same policy path as CLI)."""

from __future__ import annotations

from typing import Any

from secret_broker.broker import Broker
from secret_broker.config import load_config
from secret_broker.policy import PolicyDenied


def build_mcp(broker: Broker | None = None) -> Any:
    try:
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP as Server  # type: ignore

    broker = broker or Broker(config=load_config(), actor="mcp")
    mcp = Server(
        name="secret-broker",
        instructions=(
            "Federated secret facade. You may list/describe refs and call/run with "
            "injection. You will NEVER receive secret values. There is no get_secret tool."
        ),
    )

    @mcp.tool()
    def list_secrets(store: str | None = None) -> list[dict[str, Any]]:
        """List secret names and metadata. Never returns values."""
        return [m.model_dump() for m in broker.list(store=store)]

    @mcp.tool()
    def describe_secret(ref: str) -> dict[str, Any]:
        """Describe a secret:// reference. Never returns the value."""
        return broker.describe(ref).model_dump()

    @mcp.tool()
    def api_call(
        url: str,
        ref: str,
        method: str = "GET",
        inject: str = "bearer",
        headers: dict[str, str] | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        """Authenticated HTTP call with secret injection. Response body is redacted."""
        try:
            result = broker.call(
                url=url,
                ref_str=ref,
                method=method,
                inject=inject,
                headers=headers,
                body=body,
            )
        except PolicyDenied as exc:
            return {"error": "denied", "reason": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"error": "failed", "reason": str(exc)}
        return result.model_dump()

    @mcp.tool()
    def run_command(command: list[str], env_refs: dict[str, str]) -> dict[str, Any]:
        """Run a command with env injection. stdout/stderr are redacted."""
        try:
            result = broker.run(command, env_refs=env_refs)
        except PolicyDenied as exc:
            return {"error": "denied", "reason": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"error": "failed", "reason": str(exc)}
        return result.model_dump()

    @mcp.tool()
    def list_stores() -> list[dict[str, Any]]:
        """Configured adapters and health."""
        return [s.model_dump() for s in broker.stores()]

    @mcp.tool()
    def policy_show() -> dict[str, Any]:
        """Show destination allowlists (hosts/bins)."""
        return broker.policy_show()

    @mcp.tool()
    def audit_tail(limit: int = 50) -> list[dict[str, Any]]:
        """Recent audit events. No secret values."""
        return [e.model_dump(mode="json") for e in broker.audit_tail(limit=limit)]

    return mcp


def run_mcp(broker: Broker | None = None) -> None:
    mcp = build_mcp(broker)
    # Prefer stdio helpers across mcp versions
    if hasattr(mcp, "run_stdio_async"):
        import anyio

        anyio.run(mcp.run_stdio_async)
    else:
        mcp.run(transport="stdio")
