# R1 — Upload & Artifact Detection

## Install
```bash
pip install -e .
```

## Test
```bash
pytest tests/ingestion/
```

## Usage
```python
from app.ingestion.detector import detect_artifact_type
record = detect_artifact_type("/tmp/nasiko/uploads/abc123")
```

## Integration with Nasiko
```python
# In Nasiko's app/api/v1/router.py:
from r1.api.v1.router import api_router as r1_router
main_router.include_router(r1_router, prefix="/r1")
```

Now `POST /r1/ingest` works.
