"""Demo MCP server with @server.tool() decorators for AST parsing demo.

This file is NOT executed — it's used as input to the R3 manifest parser
to show AST-based tool extraction. The parser reads the decorators and
generates a manifest JSON without importing or running this code.

For the actual subprocess that the bridge spawns, see:
  tests/bridge/fake_mcp_agent.py (raw JSON-RPC over stdio)
"""
from mcp.server import Server

server = Server("demo-mcp-server")


@server.tool()
def hello_world(name: str) -> str:
    """Returns a friendly greeting for the given name."""
    return f"Hello, {name}!"


@server.tool()
def add(a: int, b: int) -> int:
    """Adds two numbers together and returns the result."""
    return a + b


@server.tool()
def weather(city: str) -> str:
    """Returns mock weather data for the specified city."""
    return f"Weather in {city}: 28°C, Sunny"
