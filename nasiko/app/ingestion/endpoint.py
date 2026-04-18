"""R1 — POST /ingest endpoint.

Accepts an uploaded agent artifact (pre-unpacked to disk by the CLI/web layer),
runs framework detection, and returns an IngestionRecord that R2 and R4 consume.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .models import IngestionRecord, ArtifactType, DetectionConfidence
from .detector import detect_artifact_type
from .exceptions import AmbiguousArtifactError, IngestionValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["R1 — Ingestion"])


class IngestRequest(BaseModel):
    """Body for POST /ingest.

    The caller has already placed the unpacked agent on disk at ``source_dir``.
    This endpoint validates it and returns an IngestionRecord.
    """
    source_dir: str
    artifact_id: str | None = None  # auto-generated if not provided


@router.post("", response_model=IngestionRecord)
def ingest_agent(body: IngestRequest) -> IngestionRecord:
    """Validate and classify an uploaded agent artifact.

    Steps:
      1. Validate the directory exists and contains Python files.
      2. Run AST-based framework detection.
      3. Check for existing AgentCard.json.
      4. Return an IngestionRecord.

    Raises:
        422: Invalid request body.
        400: Ambiguous framework detection.
        404: source_dir does not exist.
        500: Unexpected internal error.
    """
    source = Path(body.source_dir)
    artifact_id = body.artifact_id or str(uuid.uuid4())

    if not source.exists():
        raise HTTPException(status_code=404, detail=f"source_dir not found: {source}")

    if not source.is_dir():
        raise HTTPException(status_code=400, detail=f"source_dir is not a directory: {source}")

    try:
        artifact_type, confidence, entry_point = detect_artifact_type(
            source, artifact_id
        )
    except AmbiguousArtifactError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IngestionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(f"Unexpected error during ingestion of {artifact_id}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    has_agentcard = (source / "AgentCard.json").exists()

    record = IngestionRecord(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        confidence=confidence,
        entry_point=entry_point,
        source_dir=str(source.resolve()),
        has_agentcard=has_agentcard,
    )

    logger.info(
        f"Ingested '{artifact_id}': type={artifact_type.value}, "
        f"confidence={confidence.value}, entry={entry_point}"
    )

    return record
