from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import shutil
import uuid
import zipfile
from app.ingestion.detector import detect_artifact_type
from app.ingestion.exceptions import AmbiguousArtifactError
from app.ingestion.models import IngestionRecord

router = APIRouter()


@router.post("/ingest")
async def ingest_agent(file: UploadFile = File(...)):
    if not file.filename.endswith('.zip'):
        raise HTTPException(400, "Only .zip files are accepted")

    extract_dir = f"/tmp/nasiko/uploads/{uuid.uuid4()}"
    os.makedirs(extract_dir, exist_ok=True)

    try:
        # ZipSlip protection — validate ALL members before extracting
        with zipfile.ZipFile(file.file) as zf:
            for member in zf.namelist():
                resolved = os.path.realpath(os.path.join(extract_dir, member))
                if not resolved.startswith(os.path.realpath(extract_dir)):
                    raise HTTPException(400, "ZipSlip detected")
            # Only extract after all members are validated
            zf.extractall(extract_dir)

        record = detect_artifact_type(extract_dir)
        return JSONResponse(
            content=record.model_dump(mode='json'),
            status_code=200
        )

    except AmbiguousArtifactError as e:
        raise HTTPException(
            422,
            {"error": "AMBIGUOUS_ARTIFACT", "detail": e.reason}
        )
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)
