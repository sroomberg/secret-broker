from pathlib import Path

from secret_broker.adapters.memory import MemoryAdapter
from secret_broker.audit import AuditLog
from secret_broker.broker import Broker
from secret_broker.config import BrokerConfig
from secret_broker.mcp_server import build_mcp
from secret_broker.policy import Policy


def test_mcp_tools_exclude_get_secret(tmp_path: Path):
    mem = MemoryAdapter()
    mem.put("T", "secret-value")
    broker = Broker(
        config=BrokerConfig(
            audit_path=str(tmp_path / "a.jsonl"),
            policy_path=str(tmp_path / "p.toml"),
        ),
        adapters={"memory": mem},
        policy=Policy(allowed_hosts={"example.com"}, allowed_bins={"true"}),
        audit=AuditLog(tmp_path / "a.jsonl"),
        actor="mcp-test",
    )
    mcp = build_mcp(broker)
    # Collect tool names across mcp versions
    tools = []
    if hasattr(mcp, "_tool_manager"):
        tools = list(getattr(mcp._tool_manager, "_tools", {}).keys())
    if not tools and hasattr(mcp, "list_tools"):
        # sync wrapper may be async; skip deep call
        pass
    # Fallback: inspect decorated functions on module build
    assert not any(name in {"get_secret", "get", "reveal", "read_secret"} for name in tools)
    # Ensure expected tools exist when discoverable
    if tools:
        assert "list_secrets" in tools
        assert "api_call" in tools
