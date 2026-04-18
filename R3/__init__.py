"""MCP Manifest Generator (R3) package.

Exports the core parts of the generator:
- router: FastAPI APIRouter for integration with Nasiko.
- generate_manifest: Core logic for manifest generation.
- load_manifest: Logic for manifest retrieval.
- parse_tools: Legacy tool-only parser.
- parse_all: Full parser returning tools, resources, and prompts.
"""

from .endpoints import router
from .generator import generate_manifest, load_manifest
from .parser import parse_tools, parse_all

__all__ = ["router", "generate_manifest", "load_manifest", "parse_tools", "parse_all"]
