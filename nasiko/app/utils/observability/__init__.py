"""
Observability utilities for automatic tracing injection
"""

# Runtime imports - always available
try:
    from .tracing_utils import bootstrap_tracing
    __all__ = ["bootstrap_tracing"]
except ImportError:
    bootstrap_tracing = None
    __all__ = []

# Build-time imports - only available during injection
try:
    from .config import ObservabilityConfig
    from .injector import TracingInjector

    __all__ = ["bootstrap_tracing", "ObservabilityConfig", "TracingInjector"]
except ImportError:
    # At runtime in agent containers, only tracing_utils is needed
    __all__ = ["bootstrap_tracing"]

# MCP tracing imports - only available when mcp_tracing.py is present
# (it may not be copied into every agent container, so we guard with try/except)
try:
    from .mcp_tracing import (
        bootstrap_mcp_tracing,
        instrument_mcp_bridge,
        create_tool_call_span,
        record_tool_result,
        record_tool_error,
    )

    __all__.extend([
        "bootstrap_mcp_tracing",
        "instrument_mcp_bridge",
        "create_tool_call_span",
        "record_tool_result",
        "record_tool_error",
    ])
except ImportError:
    # mcp_tracing.py isn't present (e.g. inside a regular agent container).
    # That's fine — only the MCP bridge needs these functions.
    pass
