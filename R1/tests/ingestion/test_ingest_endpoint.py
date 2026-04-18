"""
Tests for api.v1.ingest endpoint — 9 tests total.
Uses io.BytesIO + zipfile for in-memory zip creation.
Patches shutil.rmtree to verify cleanup behavior.
"""
import io
import os
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.v1.ingest import router


# ─── Test App Setup ─────────────────────────────────────────────

@pytest.fixture
def client():
    """Create a TestClient with the ingest router mounted."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _make_zip(files: dict[str, str]) -> io.BytesIO:
    """
    Create an in-memory zip from a dict of {filename: content}.
    Returns a BytesIO positioned at the start.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf


# ─── Basic Validation (tests 1-2) ──────────────────────────────

class TestBasicValidation:
    """Verify file type validation."""

    def test_ingest_non_zip_rejected(self, client):
        """Non-zip upload returns 400."""
        response = client.post(
            "/ingest",
            files={"file": ("agent.tar.gz", b"fake data", "application/gzip")}
        )
        assert response.status_code == 400
        assert "Only .zip files" in response.json()["detail"]

    def test_ingest_valid_mcp_zip(self, client):
        """Valid MCP zip returns 200 with IngestionRecord fields."""
        zip_buf = _make_zip({"server.py": "import fastmcp\n"})
        response = client.post(
            "/ingest",
            files={"file": ("agent.zip", zip_buf, "application/zip")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["artifact_type"] == "MCP_SERVER"
        assert data["detected_framework"] == "mcp"
        assert data["confidence"] == "HIGH"


# ─── Error Handling (tests 3-5) ─────────────────────────────────

class TestErrorHandling:
    """Verify error responses for ambiguous and malicious uploads."""

    def test_ingest_no_framework(self, client):
        """No framework imports → 422 AMBIGUOUS_ARTIFACT."""
        zip_buf = _make_zip({"utils.py": "import os\n"})
        response = client.post(
            "/ingest",
            files={"file": ("agent.zip", zip_buf, "application/zip")}
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "AMBIGUOUS_ARTIFACT"
        assert "No recognized framework" in detail["detail"]

    def test_ingest_ambiguous_artifact(self, client):
        """Multiple frameworks → 422 AMBIGUOUS_ARTIFACT."""
        zip_buf = _make_zip({
            "a.py": "import fastmcp\n",
            "b.py": "import crewai\n"
        })
        response = client.post(
            "/ingest",
            files={"file": ("agent.zip", zip_buf, "application/zip")}
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "AMBIGUOUS_ARTIFACT"
        assert "Multiple frameworks" in detail["detail"]

    def test_ingest_zipslip_protection(self, client):
        """ZipSlip path traversal → 400."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            # Inject a path traversal entry
            zf.writestr("../../etc/passwd", "evil content")
        buf.seek(0)
        response = client.post(
            "/ingest",
            files={"file": ("agent.zip", buf, "application/zip")}
        )
        assert response.status_code == 400
        assert "ZipSlip" in response.json()["detail"]


# ─── Cleanup Verification (tests 6-7) ──────────────────────────

class TestCleanup:
    """Verify shutil.rmtree is ALWAYS called in finally block."""

    def test_cleanup_on_success(self, client):
        """rmtree called after successful ingestion."""
        zip_buf = _make_zip({"server.py": "import fastmcp\n"})
        with patch("api.v1.ingest.shutil.rmtree") as mock_rm:
            response = client.post(
                "/ingest",
                files={"file": ("agent.zip", zip_buf, "application/zip")}
            )
            assert response.status_code == 200
            mock_rm.assert_called_once()

    def test_cleanup_on_error(self, client):
        """rmtree called even when detection fails."""
        zip_buf = _make_zip({"utils.py": "import os\n"})
        with patch("api.v1.ingest.shutil.rmtree") as mock_rm:
            response = client.post(
                "/ingest",
                files={"file": ("agent.zip", zip_buf, "application/zip")}
            )
            assert response.status_code == 422
            mock_rm.assert_called_once()


# ─── Response Shape (tests 8-9) ─────────────────────────────────

class TestResponseShape:
    """Verify the response JSON contains all required IngestionRecord fields."""

    def test_response_contains_record_fields(self, client):
        """All IngestionRecord fields present in 200 response."""
        zip_buf = _make_zip({
            "server.py": "import fastmcp\n",
            "requirements.txt": "fastmcp>=0.1\n",
            "agentcard.json": '{"name": "test"}'
        })
        response = client.post(
            "/ingest",
            files={"file": ("agent.zip", zip_buf, "application/zip")}
        )
        assert response.status_code == 200
        data = response.json()

        required_fields = [
            "artifact_id", "source_path", "artifact_type",
            "confidence", "created_at", "entry_point",
            "detected_framework", "requirements_path",
            "agentcard_exists"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Validate specific values
        assert data["source_path"].startswith("/tmp/nasiko/uploads/")
        assert data["agentcard_exists"] is True
        assert data["requirements_path"] == "requirements.txt"

    def test_ingest_creates_upload_directory(self, client):
        """Upload directory follows /tmp/nasiko/uploads/{uuid}/ pattern."""
        zip_buf = _make_zip({"server.py": "import fastmcp\n"})
        response = client.post(
            "/ingest",
            files={"file": ("agent.zip", zip_buf, "application/zip")}
        )
        assert response.status_code == 200
        source_path = response.json()["source_path"]
        assert source_path.startswith("/tmp/nasiko/uploads/")
        # Verify the UUID segment exists
        uuid_segment = source_path.replace("/tmp/nasiko/uploads/", "")
        assert len(uuid_segment) > 0
