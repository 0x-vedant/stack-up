"""FastAPI router for MCP manifest generation and retrieval.

Thin HTTP layer over the frozen generator module. No business logic
lives here — only request parsing, delegation, and error mapping.

Part of the Nasiko MCP Manifest Generator (R3).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .generator import generate_manifest, load_manifest


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    artifact_id: str
    source_path: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/manifest", tags=["manifest"])


@router.post("/generate")
async def generate_manifest_endpoint(request: GenerateRequest) -> dict:
    """Generate an MCP manifest from a Python source file."""

    try:
        return generate_manifest(request.artifact_id, request.source_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{artifact_id}")
async def get_manifest_endpoint(artifact_id: str) -> dict:
    """Retrieve a previously generated MCP manifest."""

    try:
        return load_manifest(artifact_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
