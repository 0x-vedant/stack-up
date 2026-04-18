"""MCP manifest generator.

Reads Python source files, extracts tool definitions via the frozen
parser module, and writes atomic JSON manifests to /tmp/nasiko/{artifact_id}/.

Part of the Nasiko MCP Manifest Generator (R3).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import TypedDict

from .parser import ToolDefinition, parse_tools


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class InputSchema(TypedDict):
    type: str
    properties: dict[str, dict]
    required: list[str]


class MCPTool(TypedDict):
    name: str
    description: str | None
    input_schema: InputSchema


class MCPManifest(TypedDict):
    artifact_id: str
    generated_at: str
    tools: list[MCPTool]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ARTIFACT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")
_MANIFEST_ROOT = "/tmp/nasiko"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_artifact_id(artifact_id: str) -> None:
    """Raise ``ValueError`` if *artifact_id* is empty or contains unsafe chars."""

    if not artifact_id:
        raise ValueError("artifact_id must not be empty")

    if not _ARTIFACT_ID_RE.match(artifact_id):
        raise ValueError("Invalid artifact_id")


def _build_input_schema(tool: ToolDefinition) -> InputSchema:
    """Convert a ``ToolDefinition``'s parameters into a JSON-Schema object."""

    properties: dict[str, dict] = {
        p["name"]: p["json_schema"]
        for p in tool["parameters"]
    }
    required: list[str] = [
        p["name"]
        for p in tool["parameters"]
        if p["required"]
    ]

    return InputSchema(
        type="object",
        properties=properties,
        required=required,
    )


def _tool_to_mcp(tool: ToolDefinition) -> MCPTool:
    """Convert a ``ToolDefinition`` from the parser into an ``MCPTool``."""

    return MCPTool(
        name=tool["name"],
        description=tool["docstring"],
        input_schema=_build_input_schema(tool),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_manifest(artifact_id: str, source_path: str) -> MCPManifest:
    """Parse *source_path* for MCP tools and write a manifest to disk.

    The manifest is written atomically to
    ``/tmp/nasiko/{artifact_id}/manifest.json`` and the parsed
    ``MCPManifest`` dict is returned directly.

    Raises
    ------
    ValueError
        If *artifact_id* is empty or contains path-traversal characters,
        or if *source_path* contains a Python syntax error (propagated
        from ``parse_tools``).
    FileNotFoundError
        If *source_path* does not exist (propagated from ``open``).
    """

    _validate_artifact_id(artifact_id)

    # 1. Read source
    with open(source_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    # 2. Parse tools (may raise ValueError on syntax errors — let it propagate)
    tool_defs = parse_tools(source_code)

    # 3. Build manifest
    manifest: MCPManifest = MCPManifest(
        artifact_id=artifact_id,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        tools=[_tool_to_mcp(t) for t in tool_defs],
    )

    # 4. Write atomically
    manifest_dir = os.path.join(_MANIFEST_ROOT, artifact_id)
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, "manifest.json")

    fd, tmp_path = tempfile.mkstemp(dir=manifest_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        os.replace(tmp_path, manifest_path)
    except Exception:
        os.unlink(tmp_path)
        raise

    # 5. Return the dict — not a file path
    return manifest


def load_manifest(artifact_id: str) -> MCPManifest:
    """Load a previously generated manifest from disk.

    Raises
    ------
    ValueError
        If *artifact_id* is empty or contains path-traversal characters.
    FileNotFoundError
        If no manifest exists for the given *artifact_id*.
    """

    _validate_artifact_id(artifact_id)

    manifest_path = os.path.join(_MANIFEST_ROOT, artifact_id, "manifest.json")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Manifest not found for artifact_id={artifact_id!r}"
        )

    return json.loads(data)
