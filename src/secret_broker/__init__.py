"""secret-broker: federated secret facade for AI agents.

Architecture: agents receive references; a trusted broker process resolves and
injects secrets. Values never appear in MCP results, CLI stdout (except
redacted downstream bodies), audit logs, or error strings.
"""

__version__ = "0.1.0"
