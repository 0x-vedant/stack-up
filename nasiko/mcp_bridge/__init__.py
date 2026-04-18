"""Nasiko MCP Bridge — STDIO-to-HTTP bridge for MCP server artifacts."""

from nasiko.mcp_bridge.models import BridgeConfig
from nasiko.mcp_bridge.kong import KongRegistrar, KongRegistrationError

try:
    from nasiko.mcp_bridge.server import (
        BridgeServer,
        BridgeStartError,
        MCPHandshakeError,
        MCPToolCallError,
        app,
    )
except ImportError:
    # server.py requires opentelemetry + phoenix which may not be installed
    # in lightweight test environments. The core models/kong are still usable.
    BridgeServer = None
    BridgeStartError = None
    MCPHandshakeError = None
    MCPToolCallError = None
    app = None

__all__ = [
    "BridgeConfig",
    "BridgeServer",
    "BridgeStartError",
    "KongRegistrar",
    "KongRegistrationError",
    "MCPHandshakeError",
    "MCPToolCallError",
    "app",
]
